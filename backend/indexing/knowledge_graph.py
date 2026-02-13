"""
Knowledge Graph Builder using Neo4j
Creates a graph database of employees, projects, and documents
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from neo4j import GraphDatabase
import hashlib


class KnowledgeGraphBuilder:
    """Build and manage knowledge graph in Neo4j"""

    def __init__(self, uri: str, user: str, password: str):
        """
        Initialize Neo4j connection

        Args:
            uri: Neo4j connection URI
            user: Neo4j username
            password: Neo4j password
        """
        try:
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            # Test connection
            with self.driver.session() as session:
                session.run("RETURN 1")
            print("✓ Connected to Neo4j")
        except Exception as e:
            print(f"⚠ Could not connect to Neo4j: {e}")
            print("  Graph functionality will create Cypher queries but not execute them")
            self.driver = None

        self.queries_log = []

    def close(self):
        """Close Neo4j connection"""
        if self.driver:
            self.driver.close()

    def clear_database(self):
        """Clear all nodes and relationships (use with caution!)"""
        query = "MATCH (n) DETACH DELETE n"

        if self.driver:
            with self.driver.session() as session:
                session.run(query)
            print("✓ Cleared Neo4j database")
        else:
            self.queries_log.append(query)
            print("✓ Generated clear database query")

    def create_constraints(self):
        """Create uniqueness constraints and indexes"""
        constraints = [
            "CREATE CONSTRAINT employee_email IF NOT EXISTS FOR (e:Employee) REQUIRE e.email IS UNIQUE",
            "CREATE CONSTRAINT project_id IF NOT EXISTS FOR (p:Project) REQUIRE p.project_id IS UNIQUE",
            "CREATE CONSTRAINT document_id IF NOT EXISTS FOR (d:Document) REQUIRE d.doc_id IS UNIQUE",
            "CREATE CONSTRAINT cluster_id IF NOT EXISTS FOR (c:Cluster) REQUIRE c.cluster_id IS UNIQUE",
        ]

        if self.driver:
            with self.driver.session() as session:
                for constraint in constraints:
                    try:
                        session.run(constraint)
                    except Exception as e:
                        # Constraint might already exist
                        pass
            print("✓ Created Neo4j constraints")
        else:
            self.queries_log.extend(constraints)
            print("✓ Generated constraint queries")

    def create_employee_node(self, employee: str, metadata: Dict = None) -> str:
        """
        Create an employee node

        Args:
            employee: Employee name/identifier
            metadata: Additional employee metadata

        Returns:
            Cypher query
        """
        metadata = metadata or {}

        query = f"""
        MERGE (e:Employee {{email: $email}})
        SET e.name = $name,
            e.document_count = $doc_count
        RETURN e
        """

        params = {
            'email': employee,
            'name': employee.replace('-', ' ').title(),
            'doc_count': metadata.get('document_count', 0)
        }

        if self.driver:
            with self.driver.session() as session:
                session.run(query, params)
        else:
            self.queries_log.append((query, params))

        return query

    def create_project_node(self, project_id: str, project_name: str, metadata: Dict = None) -> str:
        """
        Create a project node

        Args:
            project_id: Unique project identifier
            project_name: Human-readable project name
            metadata: Additional project metadata

        Returns:
            Cypher query
        """
        metadata = metadata or {}

        query = """
        MERGE (p:Project {project_id: $project_id})
        SET p.name = $name,
            p.document_count = $doc_count,
            p.keywords = $keywords
        RETURN p
        """

        params = {
            'project_id': project_id,
            'name': project_name,
            'doc_count': metadata.get('document_count', 0),
            'keywords': metadata.get('keywords', [])
        }

        if self.driver:
            with self.driver.session() as session:
                session.run(query, params)
        else:
            self.queries_log.append((query, params))

        return query

    def create_document_node(self, document: Dict) -> str:
        """
        Create a document node

        Args:
            document: Document dictionary with metadata

        Returns:
            Cypher query
        """
        metadata = document.get('metadata', {})

        query = """
        MERGE (d:Document {doc_id: $doc_id})
        SET d.subject = $subject,
            d.timestamp = $timestamp,
            d.source_type = $source_type,
            d.source_path = $source_path,
            d.cluster_id = $cluster_id,
            d.cluster_label = $cluster_label
        RETURN d
        """

        params = {
            'doc_id': document.get('doc_id'),
            'subject': metadata.get('subject', ''),
            'timestamp': metadata.get('timestamp'),
            'source_type': metadata.get('source_type', 'email'),
            'source_path': metadata.get('source_path', ''),
            'cluster_id': document.get('cluster_id'),
            'cluster_label': document.get('cluster_label')
        }

        if self.driver:
            with self.driver.session() as session:
                session.run(query, params)
        else:
            self.queries_log.append((query, params))

        return query

    def create_cluster_node(self, cluster_id: str, cluster_label: str, cluster_type: str) -> str:
        """Create a cluster node"""
        query = """
        MERGE (c:Cluster {cluster_id: $cluster_id})
        SET c.label = $label,
            c.type = $type
        RETURN c
        """

        params = {
            'cluster_id': cluster_id,
            'label': cluster_label,
            'type': cluster_type
        }

        if self.driver:
            with self.driver.session() as session:
                session.run(query, params)
        else:
            self.queries_log.append((query, params))

        return query

    def create_relationship(self, from_node: str, from_id: str, rel_type: str,
                          to_node: str, to_id: str, properties: Dict = None) -> str:
        """
        Create a relationship between nodes

        Args:
            from_node: Source node label (e.g., 'Employee')
            from_id: Source node identifier property value
            rel_type: Relationship type (e.g., 'WORKED_ON')
            to_node: Target node label (e.g., 'Project')
            to_id: Target node identifier property value
            properties: Optional relationship properties

        Returns:
            Cypher query
        """
        properties = properties or {}

        # Determine identifier property based on node type
        from_prop = self._get_id_property(from_node)
        to_prop = self._get_id_property(to_node)

        props_str = ""
        if properties:
            props_str = "{" + ", ".join(f"{k}: ${k}" for k in properties.keys()) + "}"

        query = f"""
        MATCH (a:{from_node} {{{from_prop}: $from_id}})
        MATCH (b:{to_node} {{{to_prop}: $to_id}})
        MERGE (a)-[r:{rel_type} {props_str}]->(b)
        RETURN r
        """

        params = {
            'from_id': from_id,
            'to_id': to_id,
            **properties
        }

        if self.driver:
            with self.driver.session() as session:
                session.run(query, params)
        else:
            self.queries_log.append((query, params))

        return query

    def _get_id_property(self, node_label: str) -> str:
        """Get the identifier property name for a node type"""
        mapping = {
            'Employee': 'email',
            'Project': 'project_id',
            'Document': 'doc_id',
            'Cluster': 'cluster_id',
        }
        return mapping.get(node_label, 'id')

    def build_graph_from_clusters(self, project_clusters_dir: str):
        """
        Build complete knowledge graph from project clusters

        Args:
            project_clusters_dir: Directory with project cluster files
        """
        print("\nBuilding knowledge graph...")

        # Clear existing data
        self.clear_database()

        # Create constraints
        self.create_constraints()

        project_dir = Path(project_clusters_dir)

        # Process each employee
        for employee_dir in project_dir.iterdir():
            if not employee_dir.is_dir():
                continue

            employee = employee_dir.name
            print(f"\nProcessing employee: {employee}")

            # Load metadata
            metadata_file = employee_dir / "metadata.json"
            if not metadata_file.exists():
                continue

            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)

            # Create employee node
            self.create_employee_node(
                employee,
                {'document_count': metadata.get('total_documents', 0)}
            )

            # Process each project
            for project_name, project_meta in metadata.get('projects', {}).items():
                project_id = project_meta.get('cluster_id')

                # Create project node
                self.create_project_node(
                    project_id,
                    project_name,
                    {
                        'document_count': project_meta.get('document_count', 0),
                        'keywords': project_meta.get('keywords', [])
                    }
                )

                # Create cluster node
                self.create_cluster_node(project_id, project_name, 'project')

                # Create WORKED_ON relationship
                self.create_relationship(
                    'Employee', employee,
                    'WORKED_ON',
                    'Project', project_id
                )

                # Load and process documents
                project_file = employee_dir / f"{project_name}.jsonl"
                if project_file.exists():
                    with open(project_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            doc = json.loads(line)

                            # Create document node
                            self.create_document_node(doc)

                            # Create relationships
                            doc_id = doc.get('doc_id')

                            # Employee AUTHORED document
                            self.create_relationship(
                                'Employee', employee,
                                'AUTHORED',
                                'Document', doc_id,
                                {'timestamp': doc.get('metadata', {}).get('timestamp')}
                            )

                            # Document BELONGS_TO_CLUSTER
                            self.create_relationship(
                                'Document', doc_id,
                                'BELONGS_TO_CLUSTER',
                                'Cluster', project_id
                            )

                            # Project CONTAINS document
                            self.create_relationship(
                                'Project', project_id,
                                'CONTAINS',
                                'Document', doc_id
                            )

        print("\n✓ Knowledge graph construction complete")

    def save_queries_log(self, output_path: str):
        """Save generated queries to file for manual execution"""
        if not self.queries_log:
            return

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("// KnowledgeVault Neo4j Cypher Queries\n")
            f.write("// Generated queries for manual execution\n\n")

            for i, item in enumerate(self.queries_log, 1):
                if isinstance(item, tuple):
                    query, params = item
                    f.write(f"// Query {i} with params: {params}\n")
                    f.write(query)
                else:
                    f.write(f"// Query {i}\n")
                    f.write(item)
                f.write("\n\n")

        print(f"✓ Saved {len(self.queries_log)} queries to {output_path}")


if __name__ == "__main__":
    from config.config import Config

    # Build knowledge graph
    graph_builder = KnowledgeGraphBuilder(
        uri=Config.NEO4J_URI,
        user=Config.NEO4J_USER,
        password=Config.NEO4J_PASSWORD
    )

    try:
        graph_builder.build_graph_from_clusters(
            project_clusters_dir=str(Config.DATA_DIR / "project_clusters")
        )

        # Save queries log if Neo4j not available
        graph_builder.save_queries_log(
            str(Config.OUTPUT_DIR / "neo4j_queries.cypher")
        )

    finally:
        graph_builder.close()
