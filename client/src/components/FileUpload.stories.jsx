import { useState } from "react";
import FileUpload from "./FileUpload";

export default {
    title: "Components/FileUpload",
    component: FileUpload,
};

function Harness({ initial = [] }) {
    const [files, setFiles] = useState(initial);
    return <FileUpload files={files} setFiles={setFiles} />;
}

export const Empty = {
    render: () => <Harness />,
};

export const WithQueuedFiles = {
    render: () => (
        <Harness
            initial={[
                new File(["x"], "footing_plan.pdf", { type: "application/pdf" }),
                new File(["x"], "column_schedule.png", { type: "image/png" }),
            ]}
        />
    ),
};
