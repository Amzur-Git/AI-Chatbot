#!/usr/bin/env python3
"""
AI Workflow Automation Sidecar - Code Validation & Testing Suite
Tests code structure, syntax, and completeness without requiring full dependencies
"""
import os
import sys
import json
from pathlib import Path
from typing import List, Tuple


def read_text_file(path: Path) -> str:
    """Read text files robustly across mixed encodings on Windows."""
    return path.read_text(encoding="utf-8", errors="replace")

class CodeValidator:
    """Validates code quality and structure"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.tests_passed = []
        self.tests_failed = []
        self.tests_warnings = []
    
    def test_file_structure(self) -> bool:
        """Test 1: Verify all required files exist"""
        print("\n" + "="*60)
        print("🔍 TEST 1: File Structure Validation")
        print("="*60)
        
        required_files = {
            'Backend Code': [
                'backend/app/models.py',
                'backend/app/routes/tickets.py',
                'backend/app/services/ticket_automation.py',
                'backend/app/main.py',
            ],
            'Frontend Code': [
                'frontend/src/components/TicketForm.tsx',
                'frontend/src/components/TicketList.tsx',
                'frontend/src/pages/Tickets.tsx',
                'frontend/src/App.tsx',
            ],
            'Configuration & Docs': [
                '.env.example',
                'IMPLEMENTATION_SUMMARY.md',
                'QUICK_START.md',
                'WORKFLOW_AUTOMATION_GUIDE.md',
                'TESTING_CHECKLIST.md',
                'FILE_REFERENCE.md',
                'setup_verification.py',
                'n8n_workflows/ticket_automation.json',
            ]
        }
        
        all_exist = True
        for category, files in required_files.items():
            print(f"\n{category}:")
            for file_path in files:
                full_path = self.project_root / file_path
                if full_path.exists():
                    size_kb = full_path.stat().st_size / 1024
                    print(f"  ✅ {file_path} ({size_kb:.1f} KB)")
                    self.tests_passed.append(f"File exists: {file_path}")
                else:
                    print(f"  ❌ {file_path} - NOT FOUND")
                    self.tests_failed.append(f"File missing: {file_path}")
                    all_exist = False
        
        return all_exist
    
    def test_file_sizes(self) -> bool:
        """Test 2: Verify files have reasonable content"""
        print("\n" + "="*60)
        print("📏 TEST 2: File Size Validation")
        print("="*60)
        
        min_sizes = {
            'backend/app/models.py': 1000,  # Should have models
            'backend/app/routes/tickets.py': 1000,  # Should have endpoints
            'backend/app/services/ticket_automation.py': 1000,  # Should have service logic
            'frontend/src/components/TicketForm.tsx': 2000,  # Should have form logic
            'frontend/src/components/TicketList.tsx': 2000,  # Should have list logic
            'frontend/src/pages/Tickets.tsx': 1000,  # Should have page logic
            'WORKFLOW_AUTOMATION_GUIDE.md': 10000,  # Should be comprehensive
        }
        
        all_ok = True
        for file_path, min_size in min_sizes.items():
            full_path = self.project_root / file_path
            if full_path.exists():
                actual_size = full_path.stat().st_size
                if actual_size >= min_size:
                    print(f"✅ {file_path}: {actual_size} bytes (min: {min_size})")
                    self.tests_passed.append(f"File size OK: {file_path}")
                else:
                    print(f"⚠️  {file_path}: {actual_size} bytes (expected >= {min_size})")
                    self.tests_warnings.append(f"File size warning: {file_path}")
            else:
                print(f"❌ {file_path}: File not found")
                self.tests_failed.append(f"File missing: {file_path}")
                all_ok = False
        
        return all_ok
    
    def test_python_syntax(self) -> bool:
        """Test 3: Validate Python syntax"""
        print("\n" + "="*60)
        print("🐍 TEST 3: Python Syntax Validation")
        print("="*60)
        
        python_files = [
            'setup_verification.py',
            'backend/app/models.py',
            'backend/app/routes/tickets.py',
            'backend/app/services/ticket_automation.py',
        ]
        
        all_ok = True
        for file_path in python_files:
            full_path = self.project_root / file_path
            if full_path.exists():
                try:
                    code = read_text_file(full_path)
                    compile(code, str(full_path), 'exec')
                    print(f"✅ {file_path}: Syntax OK")
                    self.tests_passed.append(f"Syntax valid: {file_path}")
                except SyntaxError as e:
                    print(f"❌ {file_path}: Syntax Error - {e}")
                    self.tests_failed.append(f"Syntax error: {file_path}: {e}")
                    all_ok = False
            else:
                print(f"⚠️  {file_path}: File not found")
        
        return all_ok
    
    def test_json_syntax(self) -> bool:
        """Test 4: Validate JSON files"""
        print("\n" + "="*60)
        print("📋 TEST 4: JSON Validation")
        print("="*60)
        
        json_files = [
            'n8n_workflows/ticket_automation.json',
        ]
        
        all_ok = True
        for file_path in json_files:
            full_path = self.project_root / file_path
            if full_path.exists():
                try:
                    json.loads(read_text_file(full_path))
                    print(f"✅ {file_path}: Valid JSON")
                    self.tests_passed.append(f"JSON valid: {file_path}")
                except json.JSONDecodeError as e:
                    print(f"❌ {file_path}: JSON Error - {e}")
                    self.tests_failed.append(f"JSON error: {file_path}: {e}")
                    all_ok = False
            else:
                print(f"⚠️  {file_path}: File not found")
        
        return all_ok
    
    def test_code_content(self) -> bool:
        """Test 5: Verify key code elements exist"""
        print("\n" + "="*60)
        print("🔎 TEST 5: Code Content Validation")
        print("="*60)
        
        validations = [
            ('backend/app/models.py', ['class Ticket', 'class TicketStatus', 'class TicketPriority']),
            ('backend/app/routes/tickets.py', ['@router.post', '@router.get', 'class TicketCreateRequest']),
            ('backend/app/services/ticket_automation.py', ['class TicketAutomationService', 'async def create_ticket']),
            ('frontend/src/components/TicketForm.tsx', ['TicketForm', 'character', 'submit']),
            ('frontend/src/components/TicketList.tsx', ['TicketList', 'ticket', 'filter']),
            ('frontend/src/pages/Tickets.tsx', ['TicketForm', 'TicketList']),
        ]
        
        all_ok = True
        for file_path, required_terms in validations:
            full_path = self.project_root / file_path
            if full_path.exists():
                content = read_text_file(full_path)
                found_all = True
                for term in required_terms:
                    if term not in content:
                        print(f"❌ {file_path}: Missing '{term}'")
                        self.tests_failed.append(f"Missing term: {file_path}:{term}")
                        found_all = False
                        all_ok = False
                
                if found_all:
                    print(f"✅ {file_path}: All key elements found")
                    self.tests_passed.append(f"Code content OK: {file_path}")
            else:
                print(f"⚠️  {file_path}: File not found")
        
        return all_ok
    
    def test_documentation(self) -> bool:
        """Test 6: Verify documentation completeness"""
        print("\n" + "="*60)
        print("📚 TEST 6: Documentation Validation")
        print("="*60)
        
        doc_files = {
            'IMPLEMENTATION_SUMMARY.md': ['Architecture', 'Setup', 'Features', 'Security'],
            'QUICK_START.md': ['Configure', 'Verify', 'Services', 'Test'],
            'WORKFLOW_AUTOMATION_GUIDE.md': ['Architecture', 'Setup', 'API', 'Security', 'Troubleshooting'],
            'TESTING_CHECKLIST.md': ['Backend', 'Frontend', 'n8n', 'E2E'],
            'FILE_REFERENCE.md': ['Structure', 'Reference', 'Setup'],
        }
        
        all_ok = True
        for file_path, required_sections in doc_files.items():
            full_path = self.project_root / file_path
            if full_path.exists():
                content = read_text_file(full_path).upper()
                
                found_all = True
                for section in required_sections:
                    if section.upper() not in content:
                        print(f"⚠️  {file_path}: Missing section '{section}'")
                        self.tests_warnings.append(f"Missing section: {file_path}:{section}")
                        found_all = False
                
                if found_all:
                    print(f"✅ {file_path}: All sections present")
                    self.tests_passed.append(f"Documentation OK: {file_path}")
                else:
                    all_ok = False
            else:
                print(f"❌ {file_path}: File not found")
                self.tests_failed.append(f"Doc missing: {file_path}")
                all_ok = False
        
        return all_ok
    
    def test_env_config(self) -> bool:
        """Test 7: Verify environment configuration"""
        print("\n" + "="*60)
        print("🔐 TEST 7: Environment Configuration")
        print("="*60)
        
        env_file = self.project_root / '.env.example'
        required_vars = [
            'DATABASE_URL',
            'SECRET_KEY',
            'GOOGLE_CLIENT_ID',
            'GOOGLE_CLIENT_SECRET',
            'N8N_WEBHOOK_URL',
            'N8N_WEBHOOK_SECRET',
        ]
        
        if env_file.exists():
            content = read_text_file(env_file)
            
            all_found = True
            for var in required_vars:
                if var in content:
                    print(f"✅ {var}: Present in .env.example")
                    self.tests_passed.append(f"Env var: {var}")
                else:
                    print(f"❌ {var}: Missing from .env.example")
                    self.tests_failed.append(f"Env var missing: {var}")
                    all_found = False
            
            return all_found
        else:
            print("❌ .env.example not found")
            self.tests_failed.append(".env.example not found")
            return False
    
    def test_integration(self) -> bool:
        """Test 8: Verify integration between components"""
        print("\n" + "="*60)
        print("🔗 TEST 8: Integration Points")
        print("="*60)
        
        integrations = [
            ('frontend/src/App.tsx', '/tickets', 'Route should reference /tickets'),
            ('frontend/src/App.tsx', 'Tickets', 'App should import Tickets component'),
            ('backend/app/main.py', 'tickets', 'main.py should include tickets router'),
            ('backend/app/models.py', 'Ticket', 'Models should define Ticket'),
            ('n8n_workflows/ticket_automation.json', 'webhook', 'Workflow should have webhook node'),
        ]
        
        all_ok = True
        for file_path, search_term, description in integrations:
            full_path = self.project_root / file_path
            if full_path.exists():
                content = read_text_file(full_path)
                if search_term.lower() in content.lower():
                    print(f"✅ {description}")
                    self.tests_passed.append(f"Integration OK: {description}")
                else:
                    print(f"⚠️  {description}: '{search_term}' not found")
                    self.tests_warnings.append(f"Integration warning: {description}")
                    all_ok = False
            else:
                print(f"❌ {file_path}: Not found")
                self.tests_failed.append(f"Integration check failed: {file_path}")
                all_ok = False
        
        return all_ok
    
    def run_all_tests(self):
        """Run all validation tests"""
        print("\n")
        print("█" * 60)
        print("█ 🧪 AI WORKFLOW AUTOMATION SIDECAR - CODE VALIDATION SUITE")
        print("█" * 60)
        
        tests = [
            ("File Structure", self.test_file_structure),
            ("File Sizes", self.test_file_sizes),
            ("Python Syntax", self.test_python_syntax),
            ("JSON Syntax", self.test_json_syntax),
            ("Code Content", self.test_code_content),
            ("Documentation", self.test_documentation),
            ("Environment Config", self.test_env_config),
            ("Integration Points", self.test_integration),
        ]
        
        results = []
        for test_name, test_func in tests:
            try:
                result = test_func()
                results.append((test_name, result))
            except Exception as e:
                print(f"\n❌ TEST CRASHED: {test_name}")
                print(f"   Error: {e}")
                results.append((test_name, False))
        
        # Summary
        print("\n" + "="*60)
        print("📊 TEST SUMMARY")
        print("="*60)
        
        print(f"\nTests Run: {len(results)}")
        print(f"Passed: {sum(1 for _, r in results if r)}")
        print(f"Failed: {sum(1 for _, r in results if not r)}")
        
        print(f"\nTotal Validations:")
        print(f"  ✅ Passed: {len(self.tests_passed)}")
        print(f"  ⚠️  Warnings: {len(self.tests_warnings)}")
        print(f"  ❌ Failed: {len(self.tests_failed)}")
        
        print("\nDetailed Results:")
        for test_name, passed in results:
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"  {status} - {test_name}")
        
        if self.tests_failed:
            print("\n" + "─"*60)
            print("❌ FAILED VALIDATIONS:")
            for failure in self.tests_failed:
                print(f"   • {failure}")
        
        if self.tests_warnings:
            print("\n" + "─"*60)
            print("⚠️  WARNINGS:")
            for warning in self.tests_warnings:
                print(f"   • {warning}")
        
        # Overall result
        print("\n" + "="*60)
        if all(r for _, r in results):
            print("✅ ALL TESTS PASSED!")
            print("="*60)
            return 0
        else:
            print("❌ SOME TESTS FAILED")
            print("="*60)
            return 1


if __name__ == "__main__":
    validator = CodeValidator()
    exit_code = validator.run_all_tests()
    sys.exit(exit_code)
