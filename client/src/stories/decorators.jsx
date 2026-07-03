import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../context/AuthContext";

// Seeds a demo session so components that call useAuth() render in their
// signed-in state. Harmless for components that ignore auth.
function seedDemoSession() {
    localStorage.setItem("token", "storybook-demo-token");
    localStorage.setItem(
        "user",
        JSON.stringify({ id: "demo-user", email: "engineer@example.com" }),
    );
}

/** Wrap a story in Router + Auth providers with a seeded demo session. */
export function withRouterAuth(Story) {
    seedDemoSession();
    return (
        <MemoryRouter>
            <AuthProvider>
                <div style={{ minHeight: "100vh", padding: "1.5rem" }}>
                    <Story />
                </div>
            </AuthProvider>
        </MemoryRouter>
    );
}
