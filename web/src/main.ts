import "./style.css";
import { startApplication } from "./app";

const app = document.querySelector<HTMLElement>("#app");

if (!app) {
  throw new Error("Application root #app is missing.");
}

void startApplication(app).catch((error: unknown) => {
  const message = error instanceof Error ? error.message : "The application could not start.";
  const section = document.createElement("section");
  section.className = "fatal-error";
  section.setAttribute("role", "alert");
  const eyebrow = document.createElement("p");
  eyebrow.className = "eyebrow";
  eyebrow.textContent = "Application error";
  const heading = document.createElement("h1");
  heading.textContent = "Global Thermal Comfort × Drought";
  const detail = document.createElement("p");
  detail.textContent = message;
  section.append(eyebrow, heading, detail);
  app.replaceChildren(section);
});
