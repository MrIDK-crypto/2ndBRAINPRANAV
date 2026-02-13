"""
KnowledgeVault Master Orchestration Script
Coordinates the entire knowledge management pipeline
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config.config import Config
from data_processing.enron_parser import uncluster_enron_data
from clustering.employee_clustering import cluster_by_employee
from clustering.project_clustering import ProjectClusterer
from classification.work_personal_classifier import classify_project_documents
from gap_analysis.gap_analyzer import GapAnalyzer
from gap_analysis.question_generator import QuestionGenerator
from indexing.knowledge_graph import KnowledgeGraphBuilder
from indexing.vector_database import build_vector_database
from rag.hierarchical_rag import HierarchicalRAG
from content_generation.powerpoint_generator import PowerPointGenerator
from content_generation.video_generator import VideoGenerator


class KnowledgeVaultOrchestrator:
    """Master orchestrator for the KnowledgeVault pipeline"""

    def __init__(self, config):
        """
        Initialize orchestrator

        Args:
            config: Configuration object
        """
        self.config = config
        self.start_time = datetime.now()

        print("\n" + "="*80)
        print("KNOWLEDGEVAULT BACKEND ORCHESTRATOR")
        print("="*80)
        print(f"Started at: {self.start_time}")
        print(f"Working directory: {config.BASE_DIR}")
        print("="*80 + "\n")

    def log_step(self, step_name: str):
        """Log pipeline step"""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        print(f"\n{'='*80}")
        print(f"STEP: {step_name}")
        print(f"Elapsed time: {elapsed:.2f}s")
        print(f"{'='*80}\n")

    def step_1_uncluster_data(self, limit: int = None):
        """Step 1: Uncluster Enron dataset"""
        self.log_step("1. Unclustering Enron Data")

        output_path = self.config.DATA_DIR / "unclustered" / "enron_emails.jsonl"

        uncluster_enron_data(
            maildir_path=self.config.ENRON_MAILDIR,
            output_path=str(output_path),
            limit=limit
        )

        return str(output_path)

    def step_2_employee_clustering(self, input_file: str):
        """Step 2: Cluster by employee"""
        self.log_step("2. Clustering by Employee")

        output_dir = self.config.DATA_DIR / "employee_clusters"

        clusterer = cluster_by_employee(
            input_jsonl=input_file,
            output_dir=str(output_dir)
        )

        return str(output_dir), clusterer

    def step_3_project_clustering(self, employee_clusters_dir: str):
        """Step 3: Cluster by project"""
        self.log_step("3. Clustering by Project (BERTopic)")

        output_dir = self.config.DATA_DIR / "project_clusters"

        clusterer = ProjectClusterer(self.config)
        results = clusterer.cluster_all_employees(
            employee_clusters_dir=employee_clusters_dir,
            output_dir=str(output_dir)
        )

        return str(output_dir), results

    def step_4_classify_documents(self, project_clusters_dir: str, sample_size: int = None):
        """Step 4: Classify work vs personal"""
        self.log_step("4. Classifying Work vs Personal Documents")

        output_dir = self.config.DATA_DIR / "classified"

        try:
            classifier = classify_project_documents(
                project_dir=project_clusters_dir,
                output_dir=str(output_dir),
                api_key=self.config.OPENAI_API_KEY,
                sample_size=sample_size
            )
            return str(output_dir), classifier
        except Exception as e:
            print(f"⚠ Classification step failed: {e}")
            print("  Continuing with unclassified data...")
            return project_clusters_dir, None

    def step_5_gap_analysis(self, project_clusters_dir: str):
        """Step 5: Analyze knowledge gaps"""
        self.log_step("5. Analyzing Knowledge Gaps")

        output_dir = self.config.OUTPUT_DIR / "gap_analysis"

        analyzer = GapAnalyzer(api_key=self.config.OPENAI_API_KEY)
        results = analyzer.analyze_all_projects(
            project_clusters_dir=project_clusters_dir,
            output_dir=str(output_dir)
        )

        return str(output_dir), results

    def step_6_generate_questions(self, gap_analysis_dir: str):
        """Step 6: Generate knowledge extraction questions"""
        self.log_step("6. Generating Knowledge Extraction Questions")

        output_dir = self.config.OUTPUT_DIR / "questionnaires"

        generator = QuestionGenerator(api_key=self.config.OPENAI_API_KEY)
        generator.generate_all_questionnaires(
            gap_analysis_dir=gap_analysis_dir,
            output_dir=str(output_dir)
        )

        return str(output_dir)

    def step_7_build_knowledge_graph(self, project_clusters_dir: str):
        """Step 7: Build knowledge graph"""
        self.log_step("7. Building Knowledge Graph (Neo4j)")

        try:
            graph_builder = KnowledgeGraphBuilder(
                uri=self.config.NEO4J_URI,
                user=self.config.NEO4J_USER,
                password=self.config.NEO4J_PASSWORD
            )

            graph_builder.build_graph_from_clusters(
                project_clusters_dir=project_clusters_dir
            )

            # Save queries log
            graph_builder.save_queries_log(
                str(self.config.OUTPUT_DIR / "neo4j_queries.cypher")
            )

            graph_builder.close()

            return graph_builder
        except Exception as e:
            print(f"⚠ Knowledge graph step failed: {e}")
            print("  Continuing without graph database...")
            return None

    def step_8_build_vector_database(self, project_clusters_dir: str):
        """Step 8: Build vector database"""
        self.log_step("8. Building Vector Database (ChromaDB)")

        vdb = build_vector_database(
            project_clusters_dir=project_clusters_dir,
            persist_dir=self.config.CHROMA_PERSIST_DIR,
            config=self.config
        )

        return vdb

    def step_9_create_rag_system(self, vector_db, knowledge_graph=None):
        """Step 9: Create RAG system"""
        self.log_step("9. Creating Hierarchical RAG System")

        rag = HierarchicalRAG(
            vector_db=vector_db,
            knowledge_graph=knowledge_graph,
            api_key=self.config.OPENAI_API_KEY,
            model=self.config.LLM_MODEL
        )

        # Test query
        print("\nTesting RAG system with sample query...")
        test_response = rag.query(
            "What are the main projects and their objectives?",
            use_hierarchy=True,
            top_k=5
        )

        print(f"\nSample Response:")
        print(f"Answer: {test_response.get('answer', 'No answer')[:200]}...")
        print(f"Sources: {test_response.get('num_sources', 0)}")

        return rag

    def step_10_generate_powerpoints(self, project_clusters_dir: str):
        """Step 10: Generate PowerPoint presentations"""
        self.log_step("10. Generating PowerPoint Presentations")

        output_dir = self.config.OUTPUT_DIR / "powerpoints"

        try:
            generator = PowerPointGenerator(api_key=self.config.OPENAI_API_KEY)
            generator.generate_employee_presentations(
                project_clusters_dir=project_clusters_dir,
                output_dir=str(output_dir)
            )
            return str(output_dir)
        except Exception as e:
            print(f"⚠ PowerPoint generation failed: {e}")
            return None

    def step_11_generate_videos(self, presentations_dir: str):
        """Step 11: Generate training videos"""
        self.log_step("11. Generating Training Videos")

        if not presentations_dir:
            print("⚠ No presentations available, skipping video generation")
            return None

        output_dir = self.config.VIDEO_OUTPUT_DIR

        try:
            generator = VideoGenerator(output_dir=str(output_dir))
            generator.generate_videos_from_presentations(
                presentations_dir=presentations_dir
            )
            generator.cleanup_temp_files()
            return str(output_dir)
        except Exception as e:
            print(f"⚠ Video generation failed: {e}")
            return None

    def run_full_pipeline(
        self,
        data_limit: int = None,
        skip_classification: bool = False,
        skip_videos: bool = False
    ):
        """
        Run the complete KnowledgeVault pipeline

        Args:
            data_limit: Limit number of documents to process (for testing)
            skip_classification: Skip work/personal classification
            skip_videos: Skip video generation
        """
        try:
            # Step 1: Uncluster data
            unclustered_file = self.step_1_uncluster_data(limit=data_limit)

            # Step 2: Employee clustering
            employee_dir, employee_clusterer = self.step_2_employee_clustering(unclustered_file)

            # Step 3: Project clustering
            project_dir, project_results = self.step_3_project_clustering(employee_dir)

            # Step 4: Classification (optional)
            if not skip_classification:
                classified_dir, classifier = self.step_4_classify_documents(
                    project_dir,
                    sample_size=50  # Limit for API costs
                )
            else:
                print("\n⚠ Skipping classification step")
                classified_dir = project_dir

            # Step 5: Gap analysis
            gap_dir, gap_results = self.step_5_gap_analysis(project_dir)

            # Step 6: Question generation
            questions_dir = self.step_6_generate_questions(gap_dir)

            # Step 7: Knowledge graph
            knowledge_graph = self.step_7_build_knowledge_graph(project_dir)

            # Step 8: Vector database
            vector_db = self.step_8_build_vector_database(project_dir)

            # Step 9: RAG system
            rag_system = self.step_9_create_rag_system(vector_db, knowledge_graph)

            # Step 10: PowerPoints
            ppt_dir = self.step_10_generate_powerpoints(project_dir)

            # Step 11: Videos (optional)
            if not skip_videos and ppt_dir:
                video_dir = self.step_11_generate_videos(ppt_dir)
            else:
                print("\n⚠ Skipping video generation")
                video_dir = None

            # Final summary
            self.print_final_summary()

            return {
                'vector_db': vector_db,
                'rag_system': rag_system,
                'knowledge_graph': knowledge_graph
            }

        except Exception as e:
            print(f"\n✗ Pipeline failed: {e}")
            import traceback
            traceback.print_exc()
            return None

    def print_final_summary(self):
        """Print final pipeline summary"""
        elapsed = (datetime.now() - self.start_time).total_seconds()

        print("\n" + "="*80)
        print("PIPELINE COMPLETE")
        print("="*80)
        print(f"Total time: {elapsed:.2f}s ({elapsed/60:.2f} minutes)")
        print(f"\nOutput directories:")
        print(f"  Data: {self.config.DATA_DIR}")
        print(f"  Output: {self.config.OUTPUT_DIR}")
        print(f"  Vector DB: {self.config.CHROMA_PERSIST_DIR}")
        print("\nGenerated artifacts:")
        print(f"  ✓ Employee clusters")
        print(f"  ✓ Project clusters")
        print(f"  ✓ Gap analysis reports")
        print(f"  ✓ Knowledge extraction questionnaires")
        print(f"  ✓ Vector database")
        print(f"  ✓ Knowledge graph queries")
        print(f"  ✓ RAG query system")
        print(f"  ✓ PowerPoint presentations")
        print(f"  ✓ Training videos")
        print("="*80 + "\n")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="KnowledgeVault Backend Pipeline")

    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Limit number of documents to process (for testing)'
    )

    parser.add_argument(
        '--skip-classification',
        action='store_true',
        help='Skip work/personal classification step'
    )

    parser.add_argument(
        '--skip-videos',
        action='store_true',
        help='Skip video generation step'
    )

    parser.add_argument(
        '--interactive-rag',
        action='store_true',
        help='Run interactive RAG query mode after pipeline'
    )

    args = parser.parse_args()

    # Validate configuration
    try:
        Config.validate_config()
    except ValueError as e:
        print(f"✗ Configuration error: {e}")
        print("\nPlease:")
        print("1. Copy .env.template to .env")
        print("2. Fill in your OPENAI_API_KEY")
        print("3. Verify ENRON_MAILDIR path")
        sys.exit(1)

    # Run pipeline
    orchestrator = KnowledgeVaultOrchestrator(Config)

    results = orchestrator.run_full_pipeline(
        data_limit=args.limit,
        skip_classification=args.skip_classification,
        skip_videos=args.skip_videos
    )

    # Interactive RAG mode
    if args.interactive_rag and results and results.get('rag_system'):
        print("\n" + "="*80)
        print("Starting interactive RAG mode...")
        print("="*80)
        results['rag_system'].interactive_query()


if __name__ == "__main__":
    main()
