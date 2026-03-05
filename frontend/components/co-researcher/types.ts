export interface ResearchSession {
  id: string
  tenant_id: string
  user_id: string
  title: string | null
  research_question: string | null
  context_summary: string | null
  status: 'active' | 'paused' | 'completed' | 'archived'
  research_plan: PlanPhase[]
  research_brief: ResearchBrief
  tags: string[]
  created_at: string
  updated_at: string
  last_activity_at: string
  message_count: number
  hypothesis_count: number
  messages?: ResearchMessage[]
  hypotheses?: Hypothesis[]
}

export interface ResearchMessage {
  id: string
  session_id: string
  role: 'user' | 'assistant'
  content: string
  actions: ActionDetail[]
  sources: Source[]
  extra_data: Record<string, any>
  created_at: string
}

export interface ActionDetail {
  icon: 'search' | 'doc' | 'plan' | 'hypothesis' | 'pubmed'
  text: string
}

export interface PlanPhase {
  id: string
  title: string
  items: PlanItem[]
}

export interface PlanItem {
  text: string
  status: 'done' | 'active' | 'pending'
}

export interface ResearchBrief {
  heading?: string
  description?: string
  keyPoints?: string[]
}

export interface Hypothesis {
  id: string
  session_id: string
  statement: string
  null_hypothesis: string | null
  rationale: string | null
  status: 'draft' | 'testing' | 'supported' | 'refuted' | 'inconclusive'
  confidence_score: number
  assessment: string | null
  assessment_at: string | null
  supporting_count: number
  contradicting_count: number
  neutral_count: number
  evidence?: Evidence[]
  created_at: string
  updated_at: string
}

export interface Evidence {
  id: string
  hypothesis_id: string
  title: string
  content: string
  source_type: 'internal' | 'pubmed' | 'grant' | 'user_provided'
  evidence_type: 'supporting' | 'contradicting' | 'neutral'
  source_id: string | null
  source_url: string | null
  source_metadata: Record<string, any>
  relevance_score: number
  explanation: string | null
  created_at: string
}

export interface Source {
  title?: string
  doc_id?: string
  source_url?: string
  source_type?: string
  score?: number
}

export interface ContextData {
  documents: ContextDocument[]
  pubmed_papers: PubMedPaper[]
  gaps: string[]
}

export interface ContextDocument {
  title: string
  doc_id?: string
  score?: number
  preview?: string
}

export interface PubMedPaper {
  pmid: string
  title: string
  abstract?: string
  authors?: string[]
  journal?: string
  year?: string
  url?: string
}
