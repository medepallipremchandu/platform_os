import axios from "axios";
import type { ApiErrorBody } from "../types";

const INTAKE_API_BASE_URL = import.meta.env.VITE_INTAKE_API_BASE_URL || "http://localhost:8000/api/v1";
const ASSESSMENT_API_BASE_URL = import.meta.env.VITE_ASSESSMENT_API_BASE_URL || "http://localhost:8001/api/v1";
const API_KEY = import.meta.env.VITE_API_KEY || "";
export const ACTOR_EMAIL = import.meta.env.VITE_ACTOR_EMAIL || "system";

const commonHeaders = {
  "X-API-Key": API_KEY,
  "X-Actor-Email": ACTOR_EMAIL,
};

/** Calls intake-matching-service: JD analysis, resume analysis, submissions/matching. */
export const intakeClient = axios.create({
  baseURL: INTAKE_API_BASE_URL,
  headers: { ...commonHeaders, "Content-Type": "application/json" },
});

/** Calls assessment-service: interview sessions, question generation, evaluation, score card. */
export const assessmentClient = axios.create({
  baseURL: ASSESSMENT_API_BASE_URL,
  headers: { ...commonHeaders, "Content-Type": "application/json" },
});

export function extractErrorMessage(error: unknown): string {
  if (axios.isAxiosError<ApiErrorBody>(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((d) => d.msg).join(", ");
    if (error.message) return error.message;
  }
  return "Something went wrong. Please try again.";
}
