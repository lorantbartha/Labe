import logging
import uuid
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
from pydantic_ai.providers.openai import OpenAIProvider

from app_config import app_config
from goals.models import ClarifyingQuestion, Goal, Milestone, MilestoneStatus, Step

logger = logging.getLogger(__name__)

_openai_provider = OpenAIProvider(api_key=app_config.openai_api_key)
_fast_model = OpenAIResponsesModel(app_config.openai_fast_model, provider=_openai_provider)
_reasoning_model = OpenAIResponsesModel(app_config.openai_reasoning_model, provider=_openai_provider)


# ── Clarifying questions ───────────────────────────────────────────────────────


class _QuestionOutput(BaseModel):
    node_id: str
    icon: str
    question: str


class _QuestionsResult(BaseModel):
    title: str
    questions: list[_QuestionOutput]


_clarifying_agent: Agent[None, _QuestionsResult] = Agent(
    model=_fast_model,
    output_type=_QuestionsResult,
    system_prompt=(
        "You are a goal-planning assistant. The user has written a free-text description of "
        "something they want to achieve.\n\n"
        "Your job:\n"
        "1. Extract a concise, action-oriented title (max 10 words). "
        'Examples: "Launch a B2B SaaS MVP", "Run a sub-4-hour marathon".\n'
        "2. Generate 3-4 clarifying questions that target only the highest-value gaps in the "
        "description. Focus on what is NOT already stated and infer reasonable details instead of "
        "asking for every missing nuance. The five dimensions to consider are: constraints, "
        "skill-level, timeframe, current progress, and precise success criteria. Prioritise only "
        "the dimensions that materially affect planning quality.\n\n"
        "Keep the overall clarification flow compact. The full process should usually stay within "
        "6-7 total questions across all rounds, and simpler goals should stop earlier.\n\n"
        "Each question needs:\n"
        "- node_id: NODE_001, NODE_002, NODE_003, NODE_004 if needed\n"
        "- icon: a Material Symbols icon name (single word, e.g. 'flag', 'schedule', "
        "'warning', 'group', 'landscape', 'construction', 'trophy', 'speed')\n"
        "- question: clear, specific question text\n\n"
        "Do not ask repetitive, nice-to-have, or easily inferable questions.\n\n"
        "Example output:\n"
        "{\n"
        '  "title": "Launch a B2B SaaS MVP",\n'
        '  "questions": [\n'
        '    {"node_id": "NODE_001", "icon": "schedule", '
        '"question": "What is your target launch date?"},\n'
        '    {"node_id": "NODE_002", "icon": "construction", '
        '"question": "How much of the product have you already built?"},\n'
        '    {"node_id": "NODE_003", "icon": "group", '
        '"question": "Are you building this solo or with a team?"}\n'
        "  ]\n"
        "}"
    ),
)


# ── Sufficiency check ──────────────────────────────────────────────────────────


class _SufficiencyOutput(BaseModel):
    has_enough_info: bool
    follow_up_questions: list[_QuestionOutput]
    synopsis: str
    time_constraints: list[str]
    resources: list[str]
    current_state: list[str]
    success_criteria: list[str]
    risks_or_unknowns: list[str]


_sufficiency_agent: Agent[None, _SufficiencyOutput] = Agent(
    model=_fast_model,
    output_type=_SufficiencyOutput,
    system_prompt=(
        "You are a goal-planning assistant. The user has answered a round of clarifying "
        "questions about their goal. Your job is to decide: do we have enough information "
        "to build a detailed, actionable milestone plan?\n\n"
        "You will receive:\n"
        "- The original goal description\n"
        "- All question-and-answer pairs so far\n"
        "- The number of questions already asked\n"
        "- The current clarification round\n\n"
        "Evaluate whether there is enough clarity on these five dimensions:\n"
        "1. Constraints (budget, tools, resources)\n"
        "2. Skill-level (beginner, intermediate, expert in the domain)\n"
        "3. Timeframe (deadline or desired pace)\n"
        "4. Current progress (starting from scratch vs. partially done)\n"
        "5. Success criteria (what 'done' looks like concretely)\n\n"
        "If ALL critical gaps are covered → set has_enough_info=true, return empty "
        "follow_up_questions.\n\n"
        "If key information is still missing → set has_enough_info=false and generate "
        "1-3 targeted follow-up questions. Only ask about what is truly unclear — do not "
        "repeat questions already answered. Use node_ids continuing from the last one "
        "(e.g. if 3 questions exist, use NODE_004, NODE_005, etc.). Infer the rest whenever it "
        "is safe to do so. Avoid repetitive questions and avoid collecting information that is "
        "nice to have but not blocking.\n\n"
        "Important inference rules:\n"
        "- Do not ask again for a narrower sub-detail if the user already had a clear chance to "
        "mention it and did not.\n"
        "- If a previous question covered a broad area and the user's answer omitted one part of "
        "that area, assume that omitted part is absent, normal, or non-constraining unless it is "
        "genuinely safety-critical or plan-blocking.\n"
        "- Example: if an earlier question asked about medical conditions, medications, travel "
        "vaccines, and language support, and the user answered without mentioning vaccines, do "
        "not ask a new vaccine-only follow-up unless the plan cannot be made responsibly without it.\n"
        "- Prefer recording unresolved but non-blocking uncertainty in risks_or_unknowns instead of "
        "asking another question.\n"
        "- Do not re-ask the same topic in a more specific form across rounds unless the prior "
        "answer truly left the plan impossible to tailor.\n\n"
        "Question-budget policy:\n"
        "- 0-3 total questions asked: normal target; ask only the highest-value missing basics.\n"
        "- 4-5 total questions asked: ask only essential missing information that would materially "
        "change feasibility, milestones, dependencies, safety, or success criteria.\n"
        "- 6-7 total questions asked: ask only for super-critical blockers without which the plan "
        "would be misleading or unusable.\n"
        "- 8-10 total questions asked: ask only if planning is genuinely impossible without one "
        "final answer.\n"
        "- At 10 or more total questions asked: stop asking questions and produce the best planable "
        "summary with explicit assumptions.\n"
        "- After 5 total questions, follow-up_questions should usually be 0-1 and almost never 2.\n"
        "- After 7 total questions, follow-up_questions should usually be 0-1.\n\n"
        "Always also return a structured goal summary based on current information:\n"
        "- synopsis: 1-2 sentence concise, polished summary of the goal\n"
        "- time_constraints: 0-3 bullet-ready items for deadlines, cadence, or time availability\n"
        "- resources: 0-2 bullet-ready items for budget, tools, people, assets, or support available\n"
        "- current_state: 0-3 bullet-ready items for current progress, skill level, and starting point\n"
        "- success_criteria: 0-3 bullet-ready items for concrete definitions of success\n"
        "- risks_or_unknowns: 0-2 bullet-ready items for unresolved risks or information gaps\n"
        "Keep these lists compact and non-repetitive. Only include the most important items. Use "
        "empty lists when a category is not important enough to show.\n\n"
        "Guideline: most goals should finish within 3-5 total questions, many by 3. Only difficult "
        "or high-risk goals should approach 7, and 10 is an absolute ceiling. Stop as soon as you "
        "can build a solid plan — do not ask for the sake of asking."
    ),
)


# ── Plan generation ────────────────────────────────────────────────────────────


class _MilestoneOutput(BaseModel):
    node_id: str
    title: str
    description: str
    depends_on_node_ids: list[str]


class _StepOutput(BaseModel):
    milestone_node_id: str | None
    title: str
    priority: Literal["normal", "high"] = "normal"
    recurring: bool = False
    order: int = 1


class _PlanOutput(BaseModel):
    milestones: list[_MilestoneOutput]
    steps: list[_StepOutput]


class GoalSummary(BaseModel):
    synopsis: str = ""
    time_constraints: list[str] = []
    resources: list[str] = []
    current_state: list[str] = []
    success_criteria: list[str] = []
    risks_or_unknowns: list[str] = []


_PLAN_MODEL_SETTINGS: OpenAIResponsesModelSettings = {"openai_reasoning_effort": "medium"}

_plan_agent: Agent[None, _PlanOutput] = Agent[None, _PlanOutput](
    model=_reasoning_model,
    output_type=_PlanOutput,
    model_settings=_PLAN_MODEL_SETTINGS,
    system_prompt=(
        "You are a goal-planning assistant. Given a goal description and the user's "
        "clarifying answers, generate a concrete milestone-based plan as a directed "
        "acyclic graph (DAG).\n\n"
        "IMPORTANT: Adapt the plan to the user's stated constraints, skill-level, "
        "timeframe, and current progress. The plan should feel personalised, not generic.\n\n"
        "Rules:\n"
        "- Create 3-7 milestones forming a DAG\n"
        "- node_ids: M-01, M-02, etc.\n"
        "- Prefer parallel milestone branches whenever work can happen independently; do not "
        "turn everything into a single linear chain\n"
        "- Only add a dependency when one milestone truly blocks another milestone from starting\n"
        "- If two workstreams can proceed at the same time, make them siblings with the same "
        "prerequisite instead of chaining them together\n"
        "- Each milestone must describe a measurable, verifiable outcome, not an instruction "
        "or activity\n"
        "- Write milestone titles as achieved result states, preferably using language like "
        "'Defined', 'Built', 'Validated', 'Established', 'Completed', or similar\n"
        "- Each milestone has a short title AND a 1-2 sentence description explaining "
        "what result now exists and why that outcome matters\n"
        "- depends_on_node_ids: list of milestone node_ids this depends on "
        "(empty for root milestones, max 5)\n"
        "- Include 3-6 concrete, actionable steps per milestone\n"
        "- Keep steps imperative and task-oriented; milestones are outcomes, steps are actions\n"
        "- Steps with milestone_node_id=null are goal-level tasks "
        "(recurring habits, cross-cutting concerns) — include 1-3 of these\n"
        "- Order steps within each milestone (order field, starting at 1)\n"
        "- priority: 'high' for critical-path items, 'normal' for the rest\n\n"
        "Example output:\n"
        "{\n"
        '  "milestones": [\n'
        "    {\n"
        '      "node_id": "M-01",\n'
        '      "title": "Success Criteria Defined",\n'
        '      "description": "A clear definition of success, constraints, and the first meaningful '
        'outcome is documented so the rest of the plan has a concrete target.",\n'
        '      "depends_on_node_ids": []\n'
        "    },\n"
        "    {\n"
        '      "node_id": "M-02",\n'
        '      "title": "Infrastructure Ready for Execution",\n'
        '      "description": "The technical or operational foundation is in place and ready to '
        'support the work reliably.",\n'
        '      "depends_on_node_ids": ["M-01"]\n'
        "    },\n"
        "    {\n"
        '      "node_id": "M-03",\n'
        '      "title": "Early User Feedback Loop Established",\n'
        '      "description": "The people, stakeholders, or audience needed for feedback are lined '
        'up so progress can be validated as work advances.",\n'
        '      "depends_on_node_ids": ["M-01"]\n'
        "    },\n"
        "    {\n"
        '      "node_id": "M-04",\n'
        '      "title": "Core Workflow Built",\n'
        '      "description": "The main capability the goal depends on is implemented and usable '
        'within the chosen constraints.",\n'
        '      "depends_on_node_ids": ["M-02"]\n'
        "    },\n"
        "    {\n"
        '      "node_id": "M-05",\n'
        '      "title": "Pilot Feedback Collected and Reviewed",\n'
        '      "description": "Real feedback on the core workflow has been gathered from early '
        'users and reviewed to confirm what should change before rollout.",\n'
        '      "depends_on_node_ids": ["M-03", "M-04"]\n'
        "    },\n"
        "    {\n"
        '      "node_id": "M-06",\n'
        '      "title": "Launch Ready for Wider Rollout",\n'
        '      "description": "The plan has reached a state where broader launch or rollout can '
        'happen with confidence.",\n'
        '      "depends_on_node_ids": ["M-05"]\n'
        "    }\n"
        "  ],\n"
        '  "steps": [\n'
        '    {"milestone_node_id": "M-01", "title": "Interview 5 potential users", '
        '"order": 1, "priority": "high", "recurring": false},\n'
        '    {"milestone_node_id": "M-01", "title": "Analyze competitor landscape", '
        '"order": 2, "priority": "normal", "recurring": false},\n'
        '    {"milestone_node_id": "M-01", "title": "Write problem statement document", '
        '"order": 3, "priority": "normal", "recurring": false},\n'
        '    {"milestone_node_id": "M-02", "title": "Set up project repo and CI", '
        '"order": 1, "priority": "high", "recurring": false},\n'
        '    {"milestone_node_id": "M-02", "title": "Configure dev environment", '
        '"order": 2, "priority": "normal", "recurring": false},\n'
        '    {"milestone_node_id": "M-02", "title": "Define data models", '
        '"order": 3, "priority": "high", "recurring": false},\n'
        '    {"milestone_node_id": null, "title": "Weekly progress review", '
        '"order": 1, "priority": "normal", "recurring": true},\n'
        '    {"milestone_node_id": null, "title": "Update project journal", '
        '"order": 2, "priority": "normal", "recurring": true}\n'
        "  ]\n"
        "}"
    ),
)


@dataclass
class GoalsAI:
    async def generate_questions(self, goal_id: str, description: str) -> tuple[str, list[ClarifyingQuestion]]:
        result = await _clarifying_agent.run(f"Goal description: {description}")
        title = result.output.title
        questions = []
        for i, q in enumerate(result.output.questions, start=1):
            questions.append(
                ClarifyingQuestion(
                    id=f"{goal_id}_q{i}",
                    goal_id=goal_id,
                    node_id=q.node_id,
                    icon=q.icon,
                    question=q.question,
                    round=1,
                )
            )
        return title, questions

    async def evaluate_sufficiency(
        self,
        goal_id: str,
        description: str,
        qa_pairs: list[tuple[str, str]],
        next_question_index: int,
        current_round: int,
    ) -> tuple[bool, list[ClarifyingQuestion], GoalSummary]:
        qa_text = "\n".join(f"Q: {q}\nA: {a}" for q, a in qa_pairs)
        total_questions = len(qa_pairs)
        prompt = (
            f"Goal description: {description}\n\n"
            f"Current clarification round: {current_round}\n"
            f"Total questions already asked: {total_questions}\n"
            "Question budget guidance: 3 normal target, 5 essential-only, 7 super-critical only, "
            "10 absolute max then stop and plan with assumptions.\n\n"
            f"Q&A so far:\n{qa_text}"
        )
        result = await _sufficiency_agent.run(prompt)
        summary = GoalSummary(
            synopsis=result.output.synopsis,
            time_constraints=result.output.time_constraints,
            resources=result.output.resources,
            current_state=result.output.current_state,
            success_criteria=result.output.success_criteria,
            risks_or_unknowns=result.output.risks_or_unknowns,
        )

        if result.output.has_enough_info:
            return True, [], summary

        next_round = current_round + 1
        follow_ups = []
        for i, q in enumerate(result.output.follow_up_questions):
            follow_ups.append(
                ClarifyingQuestion(
                    id=f"{goal_id}_q{next_question_index + i}",
                    goal_id=goal_id,
                    node_id=q.node_id,
                    icon=q.icon,
                    question=q.question,
                    round=next_round,
                )
            )
        return False, follow_ups, summary

    async def generate_plan(
        self,
        goal_id: str,
        goal: Goal,
        qa_pairs: list[tuple[str, str]],
    ) -> tuple[list[Milestone], list[Step]]:
        qa_text = "\n".join(f"Q: {q}\nA: {a}" for q, a in qa_pairs)
        summary_blocks = []
        if goal.synopsis:
            summary_blocks.append(f"Synthesized summary:\n{goal.synopsis}")
        if goal.time_constraints:
            summary_blocks.append("Time constraints:\n" + "\n".join(f"- {item}" for item in goal.time_constraints))
        if goal.resources:
            summary_blocks.append("Resources:\n" + "\n".join(f"- {item}" for item in goal.resources))
        if goal.current_state:
            summary_blocks.append("Current state:\n" + "\n".join(f"- {item}" for item in goal.current_state))
        if goal.success_criteria:
            summary_blocks.append("Success criteria:\n" + "\n".join(f"- {item}" for item in goal.success_criteria))
        if goal.risks_or_unknowns:
            summary_blocks.append("Risks or unknowns:\n" + "\n".join(f"- {item}" for item in goal.risks_or_unknowns))

        prompt = (
            f"Goal description: {goal.description or goal.title}\n\n"
            + ("\n\n".join(summary_blocks) + "\n\n" if summary_blocks else "")
            + f"Clarifying Q&A:\n{qa_text}"
        )
        result = await _plan_agent.run(prompt)

        node_id_to_milestone_id: dict[str, str] = {}
        milestones: list[Milestone] = []
        for m in result.output.milestones:
            milestone_id = str(uuid.uuid4())[:8]
            node_id_to_milestone_id[m.node_id] = milestone_id
            milestones.append(
                Milestone(
                    id=milestone_id,
                    goal_id=goal_id,
                    node_id=m.node_id,
                    title=m.title,
                    description=m.description,
                    status=MilestoneStatus.pending,
                    depends_on=[],
                    steps_total=0,
                    steps_completed=0,
                )
            )

        # Resolve depends_on using real milestone IDs
        milestones_resolved: list[Milestone] = []
        for i, m_out in enumerate(result.output.milestones):
            depends_on_ids = [
                node_id_to_milestone_id[nid] for nid in m_out.depends_on_node_ids if nid in node_id_to_milestone_id
            ]
            status = MilestoneStatus.active if not depends_on_ids else MilestoneStatus.pending
            milestones_resolved.append(
                milestones[i].model_copy(
                    update={
                        "depends_on": depends_on_ids,
                        "status": status,
                    }
                )
            )

        steps: list[Step] = []
        milestone_step_counts: dict[str, int] = {}
        for s in result.output.steps:
            step_id = str(uuid.uuid4())[:8]
            milestone_id = None
            if s.milestone_node_id and s.milestone_node_id in node_id_to_milestone_id:
                milestone_id = node_id_to_milestone_id[s.milestone_node_id]
                milestone_step_counts[milestone_id] = milestone_step_counts.get(milestone_id, 0) + 1
            steps.append(
                Step(
                    id=step_id,
                    goal_id=goal_id,
                    milestone_id=milestone_id,
                    title=s.title,
                    completed=False,
                    priority=s.priority,
                    recurring=s.recurring,
                    order=s.order,
                )
            )

        # Update steps_total on milestones
        final_milestones = [
            m.model_copy(update={"steps_total": milestone_step_counts.get(m.id, 0)}) for m in milestones_resolved
        ]

        return final_milestones, steps
