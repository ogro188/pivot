import type { ReactNode, SVGProps } from 'react'

const ICONS: Record<string, ReactNode> = {
  bell: (
    <>
      <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
      <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
    </>
  ),
  bellOff: (
    <>
      <path d="M8.7 3A6 6 0 0 1 18 8c0 1.6.2 3 .6 4.4" />
      <path d="M17 17H3s3-2 3-9c0-.6.1-1.2.3-1.7" />
      <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
      <path d="m2 2 20 20" />
    </>
  ),
  volume: (
    <>
      <path d="M11 5 6 9H2v6h4l5 4z" />
      <path d="M15.5 8.5a5 5 0 0 1 0 7" />
      <path d="M18.5 5.5a9 9 0 0 1 0 13" />
    </>
  ),
  volumeOff: (
    <>
      <path d="M11 5 6 9H2v6h4l5 4z" />
      <path d="m22 9-6 6" />
      <path d="m16 9 6 6" />
    </>
  ),
  download: (
    <>
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <path d="m7 10 5 5 5-5" />
      <path d="M12 15V3" />
    </>
  ),
  play: <path d="M6 4.5v15l13-7.5z" />,
  stop: <path d="M6.5 6.5h11v11h-11z" />,
  close: (
    <>
      <path d="M18 6 6 18" />
      <path d="m6 6 12 12" />
    </>
  ),
  menu: (
    <>
      <path d="M4 6h16" />
      <path d="M4 12h16" />
      <path d="M4 18h16" />
    </>
  ),
  check: <path d="M20 6 9 17l-5-5" />,
  alert: (
    <>
      <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <path d="M12 9v4" />
      <path d="M12 17h.01" />
    </>
  ),
  info: (
    <>
      <path d="M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z" />
      <path d="M12 16v-4" />
      <path d="M12 8h.01" />
    </>
  ),
  refresh: (
    <>
      <path d="M21 12a9 9 0 1 1-2.64-6.36" />
      <path d="M21 3v6h-6" />
    </>
  ),
  chevronDown: <path d="m6 9 6 6 6-6" />,
  chevronRight: <path d="m9 18 6-6-6-6" />,
  chevronLeft: <path d="m15 18-6-6 6-6" />,
  chevronUp: <path d="m18 15-6-6-6 6" />,
  search: (
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="m21 21-4.3-4.3" />
    </>
  ),
  filter: <path d="M22 3H2l8 9.46V19l4 2v-8.54L22 3z" />,
  clock: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </>
  ),
  activity: <path d="M22 12h-4l-3 9L9 3l-3 9H2" />,
  chart: (
    <>
      <path d="M3 3v18h18" />
      <path d="m7 16 4-8 4 4 5-7" />
    </>
  ),
  database: (
    <>
      <ellipse cx="12" cy="5" rx="8" ry="3" />
      <path d="M4 5v14c0 1.66 3.58 3 8 3s8-1.34 8-3V5" />
      <path d="M4 12c0 1.66 3.58 3 8 3s8-1.34 8-3" />
    </>
  ),
  plus: (
    <>
      <path d="M12 5v14" />
      <path d="M5 12h14" />
    </>
  ),
  externalLink: (
    <>
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
      <path d="M15 3h6v6" />
      <path d="M10 14 21 3" />
    </>
  ),
  arrowUp: (
    <>
      <path d="M12 19V5" />
      <path d="m5 12 7-7 7 7" />
    </>
  ),
  arrowDown: (
    <>
      <path d="M12 5v14" />
      <path d="m19 12-7 7-7-7" />
    </>
  ),
  settings: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6h.09A1.65 1.65 0 0 0 10.09 3V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9v.09a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </>
  ),
  spinner: <circle cx="12" cy="12" r="9" strokeDasharray="42 14" />,
}

export type IconName = keyof typeof ICONS

const NAMES = Object.keys(ICONS) as IconName[]

export function isIconName(value: string): value is IconName {
  return (NAMES as string[]).includes(value)
}

interface IconProps extends Omit<SVGProps<SVGSVGElement>, 'name'> {
  name: IconName
  size?: number
  title?: string
}

export default function Icon({ name, size = 14, title, className = '', ...rest }: IconProps) {
  const isSpinner = name === 'spinner'
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={isSpinner ? `animate-spin ${className}` : className}
      role={title ? 'img' : undefined}
      aria-hidden={title ? undefined : true}
      aria-label={title}
      focusable="false"
      {...rest}
    >
      {title ? <title>{title}</title> : null}
      {ICONS[name]}
    </svg>
  )
}
