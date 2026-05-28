import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import HistoryPage from "./pages/HistoryPage";
import Sidebar from "./components/Sidebar";

function ProtectedRoute({ children }) {
  const { isAuthenticated } = useAuth();
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children;
}

function CatchAll() {
  const { isAuthenticated } = useAuth();
  return <Navigate to={isAuthenticated ? "/dashboard" : "/login"} replace />;
}

function AppLayout({ children }) {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="ml-[280px] flex-1 px-12 py-10 max-w-[960px] max-md:ml-0 max-md:px-5">
        {children}
      </main>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <AppLayout>
                <DashboardPage />
              </AppLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/history"
          element={
            <ProtectedRoute>
              <AppLayout>
                <HistoryPage />
              </AppLayout>
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<CatchAll />} />
      </Routes>
    </AuthProvider>
  );
}
