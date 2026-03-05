export default function UserInputForm({ userInput, setUserInput }) {
    return (
        <div>
            <p className="text-sm text-[var(--color-text-secondary)] mb-3">
                Please provide any missing information or corrections below. This will
                be used to refine the compliance report.
            </p>
            <textarea
                rows={6}
                placeholder={"Example:\nsite - mangalore, karnataka\nsevere condition to be taken\ntake limiting value for rest missing information"}
                value={userInput}
                onChange={(e) => setUserInput(e.target.value)}
                className="w-full px-4 py-3 text-sm text-[var(--color-text-primary)] bg-[var(--color-bg-glass)] border border-[var(--color-border-subtle)] rounded-lg resize-y leading-relaxed placeholder:text-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-accent)] focus:shadow-[0_0_0_3px_var(--color-accent-glow)] transition-all font-[inherit]"
            />
        </div>
    );
}
