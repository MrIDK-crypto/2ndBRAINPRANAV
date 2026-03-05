// High-Impact Journal Predictor — Theme Constants
// Extends Wellspring Warm with tier and field colors

export const theme = {
  primary: '#C9A598',
  primaryHover: '#B8948A',
  primaryLight: '#FBF4F1',
  pageBg: '#FAF9F7',
  cardBg: '#FFFFFF',
  textPrimary: '#2D2D2D',
  textSecondary: '#6B6B6B',
  textMuted: '#9A9A9A',
  border: '#F0EEEC',
  borderDark: '#E8E5E2',
  success: '#9CB896',
  amber: '#E2A336',
  error: '#D97B7B',
}

export const font = "Avenir, 'Avenir Next', 'DM Sans', system-ui, sans-serif"
export const fontMono = "'JetBrains Mono', 'SF Mono', monospace"
export const fontDisplay = "'Instrument Serif', Georgia, serif"

export const tierColors = {
  1: { bg: '#F0F7EE', text: '#3D6B35', border: '#9CB896', label: 'Tier 1' },
  2: { bg: '#FEF7E8', text: '#8B6914', border: '#E2A336', label: 'Tier 2' },
  3: { bg: '#FDF2F2', text: '#9B4D4D', border: '#D97B7B', label: 'Tier 3' },
}

export const fieldColors: Record<string, { bg: string; text: string; dot: string }> = {
  economics: { bg: '#EEF2FF', text: '#4338CA', dot: '#6366F1' },
  cs_data_science: { bg: '#ECFDF5', text: '#065F46', dot: '#10B981' },
  biomedical: { bg: '#FDF2F8', text: '#9D174D', dot: '#EC4899' },
  political_science: { bg: '#FFF7ED', text: '#9A3412', dot: '#F97316' },
}

export const severityColors = {
  critical: { bg: '#FDF2F2', text: '#9B4D4D', border: '#D97B7B' },
  warning: { bg: '#FEF7E8', text: '#8B6914', border: '#E2A336' },
  info: { bg: '#EEF2FF', text: '#4338CA', border: '#818CF8' },
}
