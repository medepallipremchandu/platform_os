import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { AuthProvider } from "./components/auth/AuthContext";
import { consumeHandoffFragment } from "./lib/auth";
import "./index.css";
import App from "./App.tsx";

// Must run before AuthProvider's first render reads session state, so a freshly-arrived
// handoff from `portal` is already in storage by the time anything checks it.
consumeHandoffFragment();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
);
