import { useEffect, useState } from "react";
import { Route, Routes } from "react-router-dom";
import AppLayout from "./components/layout/AppLayout";
import DashboardPage from "./pages/DashboardPage";
import InterviewSessionPage from "./pages/InterviewSessionPage";
import JDDetailPage from "./pages/JDDetailPage";
import JDListPage from "./pages/JDListPage";
import NewJDAnalysisPage from "./pages/NewJDAnalysisPage";
import NewResumeAnalysisPage from "./pages/NewResumeAnalysisPage";
import NewSubmissionPage from "./pages/NewSubmissionPage";
import ResumeDetailPage from "./pages/ResumeDetailPage";
import ResumeListPage from "./pages/ResumeListPage";
import SubmissionDetailPage from "./pages/SubmissionDetailPage";
import SubmissionListPage from "./pages/SubmissionListPage";
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
        <Route path="/" element={<DashboardPage />} />

        <Route path="/requirements" element={<JDListPage />} />
        <Route path="/requirements/new" element={<NewJDAnalysisPage />} />
        <Route path="/requirements/:id" element={<JDDetailPage />} />

        <Route path="/applicants" element={<ResumeListPage />} />
        <Route path="/applicants/new" element={<NewResumeAnalysisPage />} />
        <Route path="/applicants/:id" element={<ResumeDetailPage />} />

        <Route path="/submissions" element={<SubmissionListPage />} />
        <Route path="/submissions/new" element={<NewSubmissionPage />} />
        <Route path="/submissions/:id" element={<SubmissionDetailPage />} />

        <Route path="/interview-sessions/:id" element={<InterviewSessionPage />} />
      </Route>
    </Routes>
  );
}

export default App;
