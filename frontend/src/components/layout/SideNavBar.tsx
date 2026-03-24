import { Link, useLocation, useNavigate } from "react-router-dom";

export default function SideNavBar() {
  const location = useLocation();
  const navigate = useNavigate();

  const navItems = [
    { label: "All Goals", icon: "list_alt", to: "/goals", exact: true },
    { label: "Active", icon: "bolt", to: "/goals?status=active", exact: false },
    { label: "Archive", icon: "archive", to: "/goals?status=archived", exact: false },
  ];

  return (
    <aside className="fixed left-0 top-16 h-[calc(100vh-64px)] w-64 flex flex-col p-4 z-40 bg-stone-100 border-r-4 border-black shadow-neobrutal-sidebar">
      <div className="mb-8">
        <h2 className="text-xl font-black text-black font-headline">LABE_SYSTEM</h2>
        <p className="font-headline font-bold text-[10px] uppercase text-gray-500">v1.0.4_BLUEPRINT</p>
      </div>

      <nav className="flex flex-col gap-2 flex-grow">
        {navItems.map(({ label, icon, to, exact }) => {
          const active = exact
            ? location.pathname === to && !location.search
            : (location.pathname + location.search).includes(to.replace("/goals", ""));

          return (
            <Link
              key={label}
              to={to}
              className={[
                "flex items-center gap-3 p-3 font-headline font-bold text-xs uppercase transition-all",
                active
                  ? "bg-primary-container text-white border-2 border-black shadow-neobrutal -translate-x-1 -translate-y-1"
                  : "text-black border-2 border-transparent hover:bg-secondary-container hover:text-black hover:border-black",
              ].join(" ")}
            >
              <span className="material-symbols-outlined">{icon}</span>
              <span>{label}</span>
            </Link>
          );
        })}

        <button
          onClick={() => navigate("/goals/new")}
          className="mt-6 bg-secondary-container text-black border-2 border-black p-3 font-headline font-bold text-xs uppercase shadow-neobrutal hover:-translate-x-1 hover:-translate-y-1 transition-all flex items-center justify-center gap-2"
        >
          <span className="material-symbols-outlined">add_box</span>
          NEW_GOAL
        </button>
      </nav>

    </aside>
  );
}
