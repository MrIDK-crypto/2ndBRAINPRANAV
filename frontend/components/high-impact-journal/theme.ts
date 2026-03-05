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
  physics: { bg: '#EFF6FF', text: '#1E40AF', dot: '#3B82F6' },
  chemistry: { bg: '#FFFBEB', text: '#92400E', dot: '#F59E0B' },
  biology: { bg: '#F0FDF4', text: '#166534', dot: '#22C55E' },
  psychology: { bg: '#FAF5FF', text: '#6B21A8', dot: '#A855F7' },
  sociology: { bg: '#FFF1F2', text: '#9F1239', dot: '#FB7185' },
  engineering: { bg: '#F0F9FF', text: '#0C4A6E', dot: '#0EA5E9' },
  mathematics: { bg: '#F5F3FF', text: '#5B21B6', dot: '#8B5CF6' },
  environmental_science: { bg: '#F0FDFA', text: '#115E59', dot: '#14B8A6' },
  law: { bg: '#FEF2F2', text: '#991B1B', dot: '#EF4444' },
  education: { bg: '#FFFBEB', text: '#78350F', dot: '#D97706' },
  business_management: { bg: '#F8FAFC', text: '#334155', dot: '#64748B' },
  history: { bg: '#FDF4FF', text: '#86198F', dot: '#D946EF' },
  philosophy: { bg: '#F1F5F9', text: '#475569', dot: '#94A3B8' },
  linguistics: { bg: '#ECFEFF', text: '#155E75', dot: '#06B6D4' },
}

export const severityColors = {
  critical: { bg: '#FDF2F2', text: '#9B4D4D', border: '#D97B7B' },
  warning: { bg: '#FEF7E8', text: '#8B6914', border: '#E2A336' },
  info: { bg: '#EEF2FF', text: '#4338CA', border: '#818CF8' },
}
