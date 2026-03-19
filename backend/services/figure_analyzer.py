"""
Figure & Graph Analyzer — Vision API Integration
Extracts images from PDF files and analyzes them using GPT-4o vision.
Returns structured analysis including description, type, quality score, and suggestions.
"""

import base64
import json
import re
from typing import Dict, List, Optional

from services.openai_client import get_openai_client


class FigureAnalyzer:
    """Extracts and analyzes figures/graphs from PDF manuscripts using Vision API."""

    def __init__(self):
        self.openai = get_openai_client()
        self.min_image_size = 10 * 1024  # 10KB — skip icons/logos
        self.max_figures = 10  # Limit to 10 largest figures

    def analyze_all_figures(self, file_bytes: bytes, paper_text: str = "") -> Dict:
        """
        Extract images from a PDF and analyze each figure with the Vision API.

        Args:
            file_bytes: Raw PDF file bytes
            paper_text: First ~5000 chars of paper text for context

        Returns:
            dict with keys: figures, summary, avg_score, total_figures
        """
        try:
            import fitz  # PyMuPDF
        except ImportError:
            print("[FigureAnalyzer] PyMuPDF (fitz) not installed — skipping figure analysis")
            return {
                "figures": [],
                "summary": "Figure analysis unavailable: PyMuPDF not installed.",
                "avg_score": None,
                "total_figures": 0,
            }

        # ── Extract images from PDF ──
        images = self._extract_images(fitz, file_bytes)
        if not images:
            return {
                "figures": [],
                "summary": "No figures extracted from PDF.",
                "avg_score": None,
                "total_figures": 0,
            }

        # ── Analyze each figure ──
        analyzed_figures = []
        for idx, img_data in enumerate(images):
            try:
                result = self._analyze_single_figure(img_data, idx + 1, paper_text)
                if result:
                    analyzed_figures.append(result)
            except Exception as e:
                print(f"[FigureAnalyzer] Failed to analyze figure {idx + 1}: {e}")
                analyzed_figures.append({
                    "label": f"Figure {idx + 1}",
                    "description": f"Analysis failed: {e}",
                    "figure_type": "unknown",
                    "key_findings": [],
                    "data_quality": "unknown",
                    "issues": [str(e)],
                    "suggestions": [],
                    "score": 0,
                })

        # ── Build summary ──
        scores = [f["score"] for f in analyzed_figures if f.get("score") is not None]
        avg_score = round(sum(scores) / len(scores)) if scores else None

        figure_types = [f.get("figure_type", "unknown") for f in analyzed_figures]
        type_summary = ", ".join(set(t for t in figure_types if t != "unknown"))

        summary = (
            f"Analyzed {len(analyzed_figures)} figure(s). "
            f"Types found: {type_summary or 'various'}. "
            f"Average quality score: {avg_score}/100."
            if avg_score is not None
            else f"Analyzed {len(analyzed_figures)} figure(s)."
        )

        return {
            "figures": analyzed_figures,
            "summary": summary,
            "avg_score": avg_score,
            "total_figures": len(analyzed_figures),
        }

    def _extract_images(self, fitz, file_bytes: bytes) -> List[Dict]:
        """Extract images from PDF bytes, sorted by size, limited to max_figures."""
        images = []

        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
        except Exception as e:
            print(f"[FigureAnalyzer] Failed to open PDF: {e}")
            return []

        try:
            for page_num in range(len(doc)):
                page = doc[page_num]
                image_list = page.get_images(full=True)

                for img_index, img_info in enumerate(image_list):
                    xref = img_info[0]
                    try:
                        base_image = doc.extract_image(xref)
                        if not base_image:
                            continue

                        img_bytes = base_image["image"]
                        img_ext = base_image.get("ext", "png")

                        # Skip tiny images (icons, logos, decorations)
                        if len(img_bytes) < self.min_image_size:
                            continue

                        # Map extension to MIME type
                        mime_map = {
                            "png": "image/png",
                            "jpg": "image/jpeg",
                            "jpeg": "image/jpeg",
                            "bmp": "image/bmp",
                            "gif": "image/gif",
                            "tiff": "image/tiff",
                            "tif": "image/tiff",
                        }
                        mime_type = mime_map.get(img_ext.lower(), "image/png")

                        images.append({
                            "bytes": img_bytes,
                            "size": len(img_bytes),
                            "page": page_num + 1,
                            "ext": img_ext,
                            "mime_type": mime_type,
                            "width": base_image.get("width", 0),
                            "height": base_image.get("height", 0),
                        })
                    except Exception as e:
                        print(f"[FigureAnalyzer] Failed to extract image xref={xref} on page {page_num + 1}: {e}")
                        continue
        finally:
            doc.close()

        # Sort by size (largest first) and limit
        images.sort(key=lambda x: x["size"], reverse=True)
        return images[: self.max_figures]

    def _analyze_single_figure(self, img_data: Dict, figure_num: int, paper_text: str) -> Optional[Dict]:
        """Analyze a single figure using the Vision API."""
        b64_image = base64.b64encode(img_data["bytes"]).decode("utf-8")
        data_url = f"data:{img_data['mime_type']};base64,{b64_image}"

        context_snippet = paper_text[:3000] if paper_text else ""

        prompt = (
            f"You are an expert scientific figure reviewer. Analyze this figure (Figure {figure_num}) "
            f"from a research manuscript.\n\n"
            f"Paper context (first ~3000 chars):\n{context_snippet}\n\n"
            f"Provide your analysis as a JSON object with these exact keys:\n"
            f"- \"description\": A 1-2 sentence description of what the figure shows\n"
            f"- \"figure_type\": One of: bar_chart, line_chart, scatter_plot, heatmap, "
            f"histogram, box_plot, flow_diagram, microscopy, gel_image, western_blot, "
            f"schematic, table_figure, photograph, map, network_graph, other\n"
            f"- \"key_findings\": Array of 1-3 key observations from the figure\n"
            f"- \"data_quality\": One of: excellent, good, adequate, poor\n"
            f"- \"issues\": Array of 0-3 issues (e.g., missing axis labels, low resolution, "
            f"misleading scale, missing error bars, truncated axes)\n"
            f"- \"suggestions\": Array of 0-3 specific improvement suggestions\n"
            f"- \"score\": Integer 0-100 rating the figure's quality and clarity\n\n"
            f"Return ONLY the JSON object, no other text."
        )

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": data_url, "detail": "high"},
                    },
                ],
            }
        ]

        resp = self.openai.chat_completion(
            messages=messages,
            temperature=0.2,
            max_tokens=800,
        )

        raw = resp.choices[0].message.content.strip()

        # Parse JSON from response
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if not json_match:
            return {
                "label": f"Figure {figure_num}",
                "description": "Could not parse analysis result.",
                "figure_type": "unknown",
                "key_findings": [],
                "data_quality": "unknown",
                "issues": [],
                "suggestions": [],
                "score": 50,
                "page": img_data.get("page"),
            }

        try:
            result = json.loads(json_match.group())
        except json.JSONDecodeError:
            return {
                "label": f"Figure {figure_num}",
                "description": "JSON parse error in figure analysis.",
                "figure_type": "unknown",
                "key_findings": [],
                "data_quality": "unknown",
                "issues": [],
                "suggestions": [],
                "score": 50,
                "page": img_data.get("page"),
            }

        # Normalize and add metadata
        return {
            "label": f"Figure {figure_num}",
            "description": result.get("description", "No description"),
            "figure_type": result.get("figure_type", "unknown"),
            "key_findings": result.get("key_findings", [])[:3],
            "data_quality": result.get("data_quality", "unknown"),
            "issues": result.get("issues", [])[:3],
            "suggestions": result.get("suggestions", [])[:3],
            "score": max(0, min(100, int(result.get("score", 50)))),
            "page": img_data.get("page"),
            "dimensions": f"{img_data.get('width', '?')}x{img_data.get('height', '?')}",
        }
