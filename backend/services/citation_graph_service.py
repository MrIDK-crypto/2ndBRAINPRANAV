"""
Citation Graph Service — Build and analyze citation networks around seed papers.
Uses OpenAlex API for citation/reference data and NetworkX for graph analysis.
"""

import networkx as nx
from services.openalex_search_service import OpenAlexSearchService


class CitationGraphService:
    """Build citation graphs and find influential papers via PageRank."""

    def __init__(self):
        self.openalex = OpenAlexSearchService()

    def build_citation_graph(self, seed_openalex_id: str, depth: int = 1,
                              max_nodes: int = 50) -> dict:
        """Build citation graph around a seed paper.

        Args:
            seed_openalex_id: OpenAlex work ID (e.g., 'https://openalex.org/W...')
            depth: How many hops to traverse (1 = direct citations/references, max 2)
            max_nodes: Maximum nodes in the graph

        Returns:
            Dict with nodes, edges, influential papers (by PageRank), and stats
        """
        depth = min(depth, 2)  # Safety cap
        G = nx.DiGraph()
        visited = set()
        queue = [(seed_openalex_id, 0)]

        # Add seed node
        try:
            seed_works = self.openalex.search_works(seed_openalex_id.split('/')[-1], max_results=1)
            if seed_works:
                seed = seed_works[0]
                G.add_node(seed_openalex_id, title=seed.get('title', ''),
                          year=seed.get('year'), cited_by_count=seed.get('cited_by_count', 0),
                          is_seed=True)
        except Exception:
            G.add_node(seed_openalex_id, title='Seed Paper', is_seed=True)

        while queue and len(G.nodes) < max_nodes:
            current_id, current_depth = queue.pop(0)
            if current_id in visited or current_depth > depth:
                continue
            visited.add(current_id)

            # Get papers that cite this one
            try:
                citations = self.openalex.get_citations(current_id, max_results=10)
                for cit in citations:
                    cit_id = cit['openalex_id']
                    if len(G.nodes) >= max_nodes:
                        break
                    G.add_node(cit_id, title=cit.get('title', ''),
                              year=cit.get('year'), cited_by_count=cit.get('cited_by_count', 0))
                    G.add_edge(cit_id, current_id)  # cit cites current
                    if current_depth + 1 <= depth:
                        queue.append((cit_id, current_depth + 1))
            except Exception as e:
                print(f"[CitationGraph] Citations fetch failed for {current_id}: {e}")

            # Get papers this one references
            try:
                references = self.openalex.get_references(current_id)
                for ref in references:
                    ref_id = ref['openalex_id']
                    if len(G.nodes) >= max_nodes:
                        break
                    G.add_node(ref_id, title=ref.get('title', ''),
                              year=ref.get('year'), cited_by_count=ref.get('cited_by_count', 0))
                    G.add_edge(current_id, ref_id)  # current cites ref
                    if current_depth + 1 <= depth:
                        queue.append((ref_id, current_depth + 1))
            except Exception as e:
                print(f"[CitationGraph] References fetch failed for {current_id}: {e}")

        # Compute PageRank for influence scoring
        try:
            pagerank = nx.pagerank(G, alpha=0.85)
        except Exception:
            pagerank = {n: 1.0 / max(len(G.nodes), 1) for n in G.nodes}

        # Build output
        nodes = []
        for node_id in G.nodes:
            data = G.nodes[node_id]
            nodes.append({
                'id': node_id,
                'title': data.get('title', ''),
                'year': data.get('year'),
                'cited_by_count': data.get('cited_by_count', 0),
                'pagerank': round(pagerank.get(node_id, 0), 4),
                'is_seed': data.get('is_seed', False),
            })

        edges = [{'source': u, 'target': v} for u, v in G.edges]

        # Top influential papers by PageRank
        top_nodes = sorted(pagerank.items(), key=lambda x: x[1], reverse=True)[:10]
        influential = [{
            'id': node_id,
            'title': G.nodes[node_id].get('title', ''),
            'year': G.nodes[node_id].get('year'),
            'cited_by_count': G.nodes[node_id].get('cited_by_count', 0),
            'pagerank': round(score, 4),
        } for node_id, score in top_nodes]

        return {
            'seed': seed_openalex_id,
            'node_count': len(nodes),
            'edge_count': len(edges),
            'nodes': nodes,
            'edges': edges,
            'influential': influential,
        }
