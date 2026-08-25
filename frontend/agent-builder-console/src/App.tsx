import { useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "./components/layout/AppLayout";
import AgentDetailPage from "./pages/AgentDetailPage";
import AgentListPage from "./pages/AgentListPage";
import ModelListPage from "./pages/ModelListPage";
import NewAgentPage from "./pages/NewAgentPage";
import { consumeHandoffFragment, hasValidSession, redirectToLogin } from "./lib/auth";
import "./App.css";

function App() {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    consumeHandoffFragment();
    if (!hasValidSession()) {
      redirectToLogin();
      return;
    }
    setReady(true);
  }, []);

  if (!ready) return null;

  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<Navigate to="/agents" replace />} />

        <Route path="/agents" element={<AgentListPage />} />
        <Route path="/agents/new" element={<NewAgentPage />} />
        <Route path="/agents/:id" element={<AgentDetailPage />} />

        <Route path="/models" element={<ModelListPage />} />
      </Route>
    </Routes>
  );
}

export default App;
