import { useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "./components/layout/AppLayout";
import CallAgentFormPage from "./pages/CallAgentFormPage";
import CallAgentsPage from "./pages/CallAgentsPage";
import CallDetailPage from "./pages/CallDetailPage";
import CallsPage from "./pages/CallsPage";
import PlaceCallPage from "./pages/PlaceCallPage";
import ProvidersPage from "./pages/ProvidersPage";
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
        <Route path="/" element={<Navigate to="/calls" replace />} />

        <Route path="/providers" element={<ProvidersPage />} />

        <Route path="/call-agents" element={<CallAgentsPage />} />
        <Route path="/call-agents/new" element={<CallAgentFormPage />} />
        <Route path="/call-agents/:id/edit" element={<CallAgentFormPage />} />

        <Route path="/calls" element={<CallsPage />} />
        <Route path="/calls/new" element={<PlaceCallPage />} />
        <Route path="/calls/:id" element={<CallDetailPage />} />
      </Route>
    </Routes>
  );
}

export default App;
