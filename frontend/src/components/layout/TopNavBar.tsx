import { Link, useLocation } from "react-router-dom";

export default function TopNavBar() {
  const location = useLocation();

  const navLinks = [
    { label: "All Goals", to: "/goals", match: (p: string) => p === "/goals" },
    {
      label: "Active",
      to: "/goals?status=active",
      match: (p: string) => p.includes("status=active"),
    },
    {
      label: "Archive",
      to: "/goals?status=archived",
      match: (p: string) => p.includes("status=archived"),
    },
  ];

  return (
    <header className="fixed top-0 left-0 w-full z-50 flex justify-between items-center px-6 h-16 bg-white border-b-4 border-black">
      <div className="flex items-center gap-8">
        <Link to="/goals">
          <span className="text-2xl font-black text-black uppercase tracking-tighter font-headline cursor-pointer select-none">
            Labe
          </span>
        </Link>
        <nav className="flex gap-6 items-center h-full">
          {navLinks.map(({ label, to, match }) => {
            const active = match(location.pathname + location.search);
            return (
              <Link
                key={label}
                to={to}
                className={[
                  "font-headline font-bold uppercase tracking-tight pb-1 transition-all",
                  active
                    ? "text-black border-b-4 border-secondary-container translate-y-0.5"
                    : "text-gray-500 hover:bg-secondary-container hover:text-black px-1",
                ].join(" ")}
              >
                {label}
              </Link>
            );
          })}
        </nav>
      </div>

    </header>
  );
}
