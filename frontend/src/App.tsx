import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";

import { Layout } from "./components/Layout";
import { Empty, Loading } from "./components/ui";
import { useAuth } from "./lib/auth";
import { Dashboard } from "./pages/Dashboard";
import { LogMeal } from "./pages/LogMeal";
import { Login } from "./pages/Login";
import { MealDetail, Meals } from "./pages/Meals";
import { Menu } from "./pages/Menu";
import { Profile } from "./pages/Profile";
import { Signup } from "./pages/Signup";
import { Suggestions } from "./pages/Suggestions";
import { Water } from "./pages/Water";

function RequireAuth() {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <div className="center-screen"><Loading /></div>;
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />;
  return <Layout />;
}

function GuestOnly({ children }: { children: JSX.Element }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="center-screen"><Loading /></div>;
  return user ? <Navigate to="/" replace /> : children;
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<GuestOnly><Login /></GuestOnly>} />
      <Route path="/signup" element={<GuestOnly><Signup /></GuestOnly>} />
      <Route element={<RequireAuth />}>
        <Route index element={<Dashboard />} />
        <Route path="log" element={<LogMeal />} />
        <Route path="meals" element={<Meals />} />
        <Route path="meals/:id" element={<MealDetail />} />
        <Route path="menu" element={<Menu />} />
        <Route path="water" element={<Water />} />
        <Route path="suggestions" element={<Suggestions />} />
        <Route path="profile" element={<Profile />} />
        <Route
          path="*"
          element={
            <Empty icon="🤔">
              <p>Page not found.</p>
              <Link to="/" className="link">Go home</Link>
            </Empty>
          }
        />
      </Route>
    </Routes>
  );
}
