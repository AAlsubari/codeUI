"""Tests for language analyzers."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from codeui.lang.python import PythonLanguageAnalyzer
from codeui.lang.ts import TSLanguageAnalyzer
from codeui.lang.go import GoLanguageAnalyzer
from codeui.lang.rust import RustLanguageAnalyzer
from codeui.lang.csharp import CSharpLanguageAnalyzer
from codeui.lang.java import JavaLanguageAnalyzer
from codeui.lang.cpp import CppLanguageAnalyzer
from codeui.lang.php import PHPLanguageAnalyzer
from codeui.lang.ruby import RubyLanguageAnalyzer
from codeui.lang.kotlin import KotlinLanguageAnalyzer
from codeui.lang.swift import SwiftLanguageAnalyzer
from codeui.lang.scala import ScalaLanguageAnalyzer
from codeui.lang.dart import DartLanguageAnalyzer

class TestLanguages(unittest.TestCase):
    def test_scala_analyzer(self):
        sc = ScalaLanguageAnalyzer()
        res = sc.parse(Path("App.scala"), "package com.example\nimport scala.concurrent.Future\ntrait Repository extends BaseRepo with Logger {\n  def findById(id: Long): Future[User]\n  val timeout = 5000\n}")
        syms = list(sc.extract_symbols(res))
        self.assertTrue(any(s.name == "Repository" for s in syms))
        self.assertTrue(any(s.name == "findById" for s in syms))
        self.assertTrue(any(s.name == "timeout" for s in syms))
        edges = list(sc.extract_edges(res, syms))
        self.assertTrue(any(e.kind.value == "inherits" for e in edges))
        self.assertTrue(any(e.target_id == "scala.concurrent.Future" for e in edges))

    def test_dart_analyzer(self):
        dart = DartLanguageAnalyzer()
        res = dart.parse(Path("main.dart"), "import 'package:http/http.dart' as http;\nclass ApiClient extends BaseClient with AuthMixin implements IClient {\n  final String baseUrl;\n  Future<void> connect() async {}\n}")
        syms = list(dart.extract_symbols(res))
        self.assertTrue(any(s.name == "ApiClient" for s in syms))
        self.assertTrue(any(s.name == "connect" for s in syms))
        self.assertTrue(any(s.name == "baseUrl" for s in syms))
        edges = list(dart.extract_edges(res, syms))
        self.assertTrue(any(e.kind.value == "inherits" for e in edges))
        self.assertTrue(any(e.target_id == "package:http/http.dart" for e in edges))

    def test_kotlin_analyzer(self):
        kt = KotlinLanguageAnalyzer()
        res = kt.parse(Path("Main.kt"), "package com.app\nimport com.model.User\ndata class User(val id: Long, val name: String) : Base()\nfun run() {}")
        syms = list(kt.extract_symbols(res))
        self.assertTrue(any(s.name == "User" for s in syms))
        self.assertTrue(any(s.name == "run" for s in syms))
        edges = list(kt.extract_edges(res, syms))
        self.assertTrue(any(e.kind.value == "inherits" for e in edges))
        self.assertTrue(any(e.target_id == "com.model.User" for e in edges))

    def test_swift_analyzer(self):
        sw = SwiftLanguageAnalyzer()
        res = sw.parse(Path("App.swift"), "import Foundation\nclass Service: BaseService {\n  func execute() {}\n}")
        syms = list(sw.extract_symbols(res))
        self.assertTrue(any(s.name == "Service" for s in syms))
        self.assertTrue(any(s.name == "execute" for s in syms))
        edges = list(sw.extract_edges(res, syms))
        self.assertTrue(any(e.kind.value == "inherits" for e in edges))
        self.assertTrue(any(e.target_id == "Foundation" for e in edges))

    def test_csharp_analyzer(self):
        cs = CSharpLanguageAnalyzer()
        res = cs.parse(Path("Main.cs"), "using System;\npublic class App { public void Run() {} }")
        syms = list(cs.extract_symbols(res))
        self.assertTrue(any(s.name == "App" for s in syms))
        self.assertTrue(any(s.name == "Run" for s in syms))
        edges = list(cs.extract_edges(res, syms))
        self.assertTrue(any(e.target_id == "module::System" for e in edges))

    def test_java_analyzer(self):
        j = JavaLanguageAnalyzer()
        res = j.parse(Path("Main.java"), "package com.app;\nimport java.util.List;\npublic class App extends Base implements IRun {\n  public void run() {}\n}")
        syms = list(j.extract_symbols(res))
        self.assertTrue(any(s.name == "App" for s in syms))
        self.assertTrue(any(s.name == "run" for s in syms))
        edges = list(j.extract_edges(res, syms))
        self.assertTrue(any(e.kind.value == "inherits" for e in edges))

    def test_cpp_analyzer(self):
        cpp = CppLanguageAnalyzer()
        res = cpp.parse(Path("main.cpp"), '#include "engine.h"\nclass Engine : public Base {\npublic:\n  void start() {}\n};')
        syms = list(cpp.extract_symbols(res))
        self.assertTrue(any(s.name == "Engine" for s in syms))
        self.assertTrue(any(s.name == "start" for s in syms))
        edges = list(cpp.extract_edges(res, syms))
        self.assertTrue(any(e.kind.value == "inherits" for e in edges))

    def test_php_analyzer(self):
        php = PHPLanguageAnalyzer()
        res = php.parse(Path("App.php"), "<?php\nuse App\\Service;\nclass Controller extends Base {\n  public function index() { $this->render(); }\n}")
        syms = list(php.extract_symbols(res))
        self.assertTrue(any(s.name == "Controller" for s in syms))
        self.assertTrue(any(s.name == "index" for s in syms))
        edges = list(php.extract_edges(res, syms))
        self.assertTrue(any(e.kind.value == "inherits" for e in edges))
        self.assertTrue(any(e.target_id == "module::App/Service" for e in edges))

    def test_ruby_analyzer(self):
        rb = RubyLanguageAnalyzer()
        res = rb.parse(Path("app.rb"), "require 'json'\nclass Server < Base\n  def start\n  end\nend")
        syms = list(rb.extract_symbols(res))
        self.assertTrue(any(s.name == "Server" for s in syms))
        self.assertTrue(any(s.name == "start" for s in syms))
        edges = list(rb.extract_edges(res, syms))
        self.assertTrue(any(e.kind.value == "inherits" for e in edges))
        self.assertTrue(any(e.target_id == "module::json" for e in edges))

    def test_python_analyzer(self):
        p = PythonLanguageAnalyzer()
        res = p.parse(Path("test.py"), "def add(a, b): return a + b")
        syms = list(p.extract_symbols(res))
        self.assertTrue(any(s.name == "add" for s in syms))

    def test_ts_analyzer(self):
        ts = TSLanguageAnalyzer()
        res = ts.parse(Path("test.ts"), "export class User { id: number; }")
        syms = list(ts.extract_symbols(res))
        self.assertTrue(any(s.name == "User" for s in syms))

    def test_tsx_jsx_and_import_edges(self):
        ts = TSLanguageAnalyzer()
        code = "import { Button } from './Button';\\nexport function App() { return <Button label='Submit' />; }"
        res = ts.parse(Path("App.tsx"), code)
        syms = list(ts.extract_symbols(res))
        edges = list(ts.extract_edges(res, syms))
        self.assertTrue(any(e.target_id == "module::./Button::Button" for e in edges))

    def test_go_analyzer(self):
        go = GoLanguageAnalyzer()
        res = go.parse(Path("main.go"), "package main\\nfunc Main() {}")
        syms = list(go.extract_symbols(res))
        self.assertTrue(any(s.name == "Main" for s in syms))

    def test_rust_analyzer(self):
        rs = RustLanguageAnalyzer()
        res = rs.parse(Path("lib.rs"), "pub fn compute() {}")
        syms = list(rs.extract_symbols(res))
        self.assertTrue(any(s.name == "compute" for s in syms))

if __name__ == "__main__":
    unittest.main()
