import { NavLink, Outlet } from "react-router-dom";

import { useUser } from "../lib/auth";
import { NotificationCenter } from "./NotificationCenter";

const NAV = [
  { to: "/", label: "Today", icon: "🏠", end: true },
  { to: "/log", label: "Log meal", icon: "📷" },
  { to: "/meals", label: "Meals", icon: "🍽️" },
  { to: "/menu", label: "Office menu", icon: "📅" },
  { to: "/water", label: "Water", icon: "💧" },
  { to: "/suggestions", label: "Suggestions", icon: "✨" },
  { to: "/profile", label: "Profile", icon: "👤" },
];

export function Layout() {
  const user = useUser();
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span aria-hidden>🥗</span> Food Agent
        </div>
        <nav>
          {NAV.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end} className="nav-link">
              <span aria-hidden>{item.icon}</span>
              <span className="nav-text">{item.label}</span>
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="main">
        <div className="topbar">
          <span className="brand brand-mobile">
            <span aria-hidden>🥗</span> Food Agent
          </span>
          <span className="muted small hide-mobile">Hi, {user.preferred_name}</span>
          <NotificationCenter />
        </div>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
