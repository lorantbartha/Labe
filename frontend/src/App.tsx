import { Navigate, Route, Routes } from "react-router-dom";
import ClarifyingQAPage from "./pages/ClarifyingQAPage";
import DashboardPage from "./pages/DashboardPage";
import GoalCreationPage from "./pages/GoalCreationPage";
import PlanViewPage from "./pages/PlanViewPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/goals" replace />} />
      <Route path="/goals" element={<DashboardPage />} />
      <Route path="/goals/new" element={<GoalCreationPage />} />
      <Route path="/goals/:id/clarify" element={<ClarifyingQAPage />} />
      <Route path="/goals/:id/plan" element={<PlanViewPage />} />
    </Routes>
  );
}
