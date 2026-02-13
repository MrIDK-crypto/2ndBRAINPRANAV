"""
Test LLM-First Clustering with sample documents
"""

from clustering.llm_first_clusterer import LLMFirstClusterer
import json

# Sample test documents (content only, no metadata)
test_documents = [
    {
        'doc_id': 'doc_1',
        'content': '''
        Meeting notes for Project Phoenix - API Development

        Discussed the new API endpoints for the customer dashboard.
        Team agreed to use GraphQL instead of REST.
        Timeline: Complete by end of Q2.
        Client: TechCorp Inc.

        Action items:
        - Design schema (Sarah)
        - Set up Apollo Server (Mike)
        - Authentication integration (David)
        '''
    },
    {
        'doc_id': 'doc_2',
        'content': '''
        Phoenix Dashboard - GraphQL Schema Draft

        Here's the initial schema for the TechCorp customer dashboard API:

        type Customer {
          id: ID!
          name: String!
          orders: [Order]
        }

        type Order {
          id: ID!
          total: Float!
        }

        Query resolvers to be implemented next week.
        '''
    },
    {
        'doc_id': 'doc_3',
        'content': '''
        Marketing Campaign Analysis - Q1 2024

        Reviewed performance of email marketing campaigns.
        Open rate: 24%
        Click-through rate: 3.2%

        Recommendations:
        - A/B test subject lines
        - Segment audience by industry
        - Increase send frequency

        Budget: $50K for Q2
        '''
    },
    {
        'doc_id': 'doc_4',
        'content': '''
        TechCorp Project Update

        The Phoenix API is progressing well. Mike completed the Apollo Server setup.
        GraphQL playground is live at /graphql endpoint.

        Next sprint: Authentication and customer queries.
        Demo scheduled for client next Friday.
        '''
    },
    {
        'doc_id': 'doc_5',
        'content': '''
        Email Marketing Dashboard - Feature Spec

        Building analytics dashboard for marketing team.

        Key features:
        - Campaign performance metrics
        - Audience segmentation analysis
        - A/B test results visualization
        - Export to CSV/PDF

        Tech stack: React + D3.js
        Timeline: 6 weeks
        '''
    },
    {
        'doc_id': 'doc_6',
        'content': '''
        Weekly team sync - June 15

        Phoenix Project (TechCorp):
        - API endpoints 80% complete
        - Authentication module in review
        - Client demo went great, they loved the GraphQL approach

        Marketing Dashboard:
        - Started UI mockups
        - D3.js charts looking good
        - Need to finalize metrics with marketing team
        '''
    }
]

if __name__ == "__main__":
    print("="*70)
    print("TESTING LLM-FIRST CLUSTERING")
    print("="*70)
    print(f"\nTest dataset: {len(test_documents)} documents")
    print("\nExpected clustering:")
    print("  Project 1: Phoenix API (docs 1, 2, 4, 6)")
    print("  Project 2: Marketing Analytics (docs 3, 5, 6)")
    print("  Note: doc_6 might belong to both (overlapping projects)")
    print()

    # Initialize clusterer
    clusterer = LLMFirstClusterer()

    # Run clustering
    clusters = clusterer.process_documents(
        test_documents,
        embedding_threshold=0.6,
        llm_threshold=0.5,
        merge_threshold=0.85
    )

    # Print results
    print("\n" + "="*70)
    print("CLUSTERING RESULTS")
    print("="*70)

    for cluster_id, cluster in clusters.items():
        print(f"\nProject: {cluster.name}")
        print(f"  Description: {cluster.description}")
        print(f"  Documents: {len(cluster.document_ids)}")
        print(f"  Doc IDs: {cluster.document_ids}")
        print(f"  Confidence: {cluster.confidence:.2f}")
        print(f"  Status: {cluster.validation_status}")

    # Summary
    summary = clusterer.get_project_summary()
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(json.dumps(summary, indent=2))
