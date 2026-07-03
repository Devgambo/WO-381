export default function UserInputForm({ userInput, setUserInput }) {
    const placeholder = `Example:
site - mangalore, karnataka
severe condition to be taken
take limiting value for rest missing information`;
    return (
        <div>
            <label
                htmlFor="user-notes-textarea"
                className="block label-mono mb-2"
            >
                Additional notes / corrections
            </label>
            <p className="text-xs text-[var(--color-text-secondary)] mb-3">
                Anything you want the compliance engine to consider before generating the final report.
            </p>
            <textarea
                id="user-notes-textarea"
                rows={6}
                placeholder={placeholder}
                value={userInput}
                onChange={(e) => setUserInput(e.target.value)}
                className="input-base w-full px-3.5 py-3 text-sm resize-y leading-relaxed placeholder:text-[var(--color-text-faint)]"
            />
        </div>
    );
}
