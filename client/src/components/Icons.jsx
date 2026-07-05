// Inline stroke icons — 24×24 viewBox, 1.75px stroke, currentColor.
// Self-contained so we don't ship an icon-library dependency.

function Icon({ size = 14, children, className = "", ...rest }) {
    return (
        <svg
            width={size}
            height={size}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.75"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
            className={className}
            {...rest}
        >
            {children}
        </svg>
    );
}

export const ArrowRightIcon = (p) => (
    <Icon {...p}><path d="M5 12h14" /><path d="m13 6 6 6-6 6" /></Icon>
);

export const ArrowLeftIcon = (p) => (
    <Icon {...p}><path d="M19 12H5" /><path d="m11 18-6-6 6-6" /></Icon>
);

export const XIcon = (p) => (
    <Icon {...p}><path d="M18 6 6 18" /><path d="m6 6 12 12" /></Icon>
);

export const MenuIcon = (p) => (
    <Icon {...p}><path d="M4 7h16" /><path d="M4 12h16" /><path d="M4 17h16" /></Icon>
);

export const UploadIcon = (p) => (
    <Icon {...p}>
        <path d="M12 15V4" /><path d="m7 9 5-5 5 5" />
        <path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />
    </Icon>
);

export const DownloadIcon = (p) => (
    <Icon {...p}>
        <path d="M12 4v11" /><path d="m7 10 5 5 5-5" />
        <path d="M4 19h16" />
    </Icon>
);

export const TrashIcon = (p) => (
    <Icon {...p}>
        <path d="M4 7h16" /><path d="M10 11v6" /><path d="M14 11v6" />
        <path d="M6 7l1 13a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-13" />
        <path d="M9 7V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v3" />
    </Icon>
);

export const EyeIcon = (p) => (
    <Icon {...p}>
        <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z" />
        <circle cx="12" cy="12" r="3" />
    </Icon>
);

export const PlayIcon = (p) => (
    <Icon {...p}><path d="m7 4 13 8-13 8Z" /></Icon>
);

export const FileTextIcon = (p) => (
    <Icon {...p}>
        <path d="M14 3H6a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8Z" />
        <path d="M14 3v5h5" /><path d="M9 13h6" /><path d="M9 17h6" />
    </Icon>
);

export const AlertTriangleIcon = (p) => (
    <Icon {...p}>
        <path d="M12 3 2 20h20L12 3Z" /><path d="M12 10v4" /><path d="M12 17.5v.5" />
    </Icon>
);

export const InfoIcon = (p) => (
    <Icon {...p}>
        <circle cx="12" cy="12" r="9" /><path d="M12 11v5" /><path d="M12 7.5v.5" />
    </Icon>
);

export const CheckIcon = (p) => (
    <Icon {...p}><path d="m4 12.5 5.5 5.5L20 6.5" /></Icon>
);

export const LogOutIcon = (p) => (
    <Icon {...p}>
        <path d="M9 21H5a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h4" />
        <path d="m16 17 5-5-5-5" /><path d="M21 12H9" />
    </Icon>
);

export const HistoryIcon = (p) => (
    <Icon {...p}>
        <path d="M3 12a9 9 0 1 0 3-6.7L3 8" /><path d="M3 3v5h5" />
        <path d="M12 7v5l3.5 2" />
    </Icon>
);

export const PlusIcon = (p) => (
    <Icon {...p}><path d="M12 5v14" /><path d="M5 12h14" /></Icon>
);

export const LayersIcon = (p) => (
    <Icon {...p}>
        <path d="m12 3 9 5-9 5-9-5 9-5Z" />
        <path d="m3 13 9 5 9-5" /><path d="m3 17.5 9 5 9-5" />
    </Icon>
);

export const CompassIcon = (p) => (
    <Icon {...p}>
        <circle cx="12" cy="12" r="9" />
        <path d="m15.5 8.5-2 5-5 2 2-5 5-2Z" />
    </Icon>
);

export const RefreshIcon = (p) => (
    <Icon {...p}>
        <path d="M21 12a9 9 0 1 1-2.6-6.4L21 8" /><path d="M21 3v5h-5" />
    </Icon>
);
