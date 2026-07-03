import Sidebar from "./Sidebar";
import { withRouterAuth } from "../stories/decorators";

export default {
    title: "Components/Sidebar",
    component: Sidebar,
    decorators: [withRouterAuth],
    parameters: { layout: "fullscreen" },
};

export const SignedIn = {};
