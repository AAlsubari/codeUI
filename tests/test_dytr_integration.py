"""Dynamic repository integration tests using the dytr benchmark."""
import sys
import unittest
import tempfile
import shutil
from pathlib import Path

# Add src/ to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from codeui.cli.main import scan_project
from codeui.core.ir import SymbolKind, EdgeKind
from codeui.tracer.tracer import Tracer
from codeui.agent.context import ContextBuilder
from codeui.analysis.runner import AnalysisRunner
from codeui.analysis.base import AnalysisContext
from codeui.core.repo import clone_git_repo

class TestDyTRIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # We check if dytr repo is already cloned at the specific path
        cls.dytr_path = Path("/tmp/codeui_repos/active_repo")
        if not cls.dytr_path.exists() or not (cls.dytr_path / ".git").exists():
            # Clone dynamically
            print("Cloning dytr repository dynamically for integration testing...")
            cls.dytr_path, cls.temp_clone = clone_git_repo("https://github.com/AAlsubari/dytr")
        else:
            cls.temp_clone = None

        # Execute full codeui pipeline
        print(f"Scanning project at {cls.dytr_path}...")
        cls.graph = scan_project(cls.dytr_path)

    @classmethod
    def tearDownClass(cls):
        # Clean up if we used a temporary clone
        if cls.temp_clone:
            try:
                cls.temp_clone.cleanup()
            except Exception:
                pass

    def test_dytr_pipeline_and_parsing(self):
        # Verify symbols and edges were extracted
        symbols = list(self.graph.get_all_symbols())
        edges = list(self.graph.get_edges())
        self.assertGreater(len(symbols), 100, "Should extract a significant number of symbols")
        self.assertGreater(len(edges), 300, "Should extract a significant number of edges")

    def test_symbol_assertions(self):
        # Verify DynamicTransformer, Trainer, SimpleTokenizer, EWC symbols exist in the graph
        symbol_names = {s.name for s in self.graph.get_all_symbols()}
        self.assertIn("DynamicTransformer", symbol_names, "DynamicTransformer (model) symbol should exist")
        self.assertIn("Trainer", symbol_names, "Trainer (trainer) symbol should exist")
        self.assertIn("SimpleTokenizer", symbol_names, "SimpleTokenizer symbol should exist")
        self.assertIn("EWC", symbol_names, "EWC memory symbol should exist")

    def test_tracer_verification(self):
        # Find the DynamicTransformer symbol ID
        dt_sym = None
        for s in self.graph.get_all_symbols():
            if s.name == "DynamicTransformer" and s.kind == SymbolKind.CLASS:
                dt_sym = s
                break
        
        self.assertIsNotNone(dt_sym, "DynamicTransformer class symbol should be found")
        
        tracer = Tracer(self.graph)
        forward_chain = list(tracer.forward(dt_sym.id))
        backward_chain = list(tracer.backward(dt_sym.id))
        
        # We assert that we can trace forward or backward paths without error
        self.assertIsInstance(forward_chain, list)
        self.assertIsInstance(backward_chain, list)

    def test_context_builder_verification(self):
        # Find the DynamicTransformer symbol ID
        dt_sym = None
        for s in self.graph.get_all_symbols():
            if s.name == "DynamicTransformer" and s.kind == SymbolKind.CLASS:
                dt_sym = s
                break

        self.assertIsNotNone(dt_sym, "DynamicTransformer class symbol should be found")
        
        builder = ContextBuilder(self.graph)
        bundle = builder.for_symbol(dt_sym.id, depth=1)
        self.assertIsNotNone(bundle)
        self.assertEqual(bundle.manifest.get("symbol_id"), dt_sym.id)
        # Verify some signatures or bodies are extracted
        self.assertIsInstance(bundle.symbol_bodies, dict)

    def test_defect_verification(self):
        # Run defect analysis on the graph
        from codeui.analysis.runner import AnalysisRunner
        from codeui.analysis.undefined import UndefinedSymbolAnalyzer
        from codeui.analysis.circular import CircularDependencyAnalyzer
        
        ctx = AnalysisContext(self.dytr_path)
        
        # Run UndefinedSymbolAnalyzer
        undefined_analyzer = UndefinedSymbolAnalyzer()
        undefined_findings = list(undefined_analyzer.run(self.graph, ctx))
        
        # Verify that false-positive undefined_symbol findings for loop variables are 0
        loop_var_findings = [f for f in undefined_findings if f.rule_id == "undefined_symbol" and "layer" in f.message]
        self.assertEqual(len(loop_var_findings), 0, "Should have 0 false-positive undefined_symbol findings for loop variable 'layer'")
        
        # Run CircularDependencyAnalyzer to detect the circular import
        circular_analyzer = CircularDependencyAnalyzer()
        circular_findings = list(circular_analyzer.run(self.graph, ctx))
        
        # The real defect (circular import between __init__.py and trainer.py) should be detected
        circular_defect = [f for f in circular_findings if "trainer.py" in f.id or "trainer" in f.message]
        self.assertGreaterEqual(len(circular_defect), 1, "Real circular import defect should be detected successfully")

if __name__ == "__main__":
    unittest.main()
