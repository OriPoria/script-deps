import ast
import argparse
import importlib
import os
import sys
import shutil
from pathlib import Path
from types import ModuleType
from typing import Set, List
import pytest
import pkg_resources


class DependencyCollector:
    def __init__(self, gateway_path: str, root_path: str, output_path: str = None):
        self.gateway_path = Path(gateway_path).resolve()
        self.root_path = Path(root_path).resolve()
        self.output_path = Path(output_path) if output_path else self.gateway_path.parent
        self.collected_modules: Set[str] = set()
        self.collected_files: Set[Path] = set()
        self.third_party_packages: Set[str] = set()
        self.config_extensions = {'.txt', '.yaml', '.yml', '.json'}  # Add more if needed

        # Add gateway script to collected files
        self.collected_files.add(self.gateway_path)

    def is_venv_module(self, module_path: Path) -> bool:
        """Check if module is from virtual environment."""
        return 'venv' in str(module_path).lower() or 'site-packages' in str(module_path)

    def get_package_name(self, module_path: Path) -> str:
        """Get the package name from a module path."""
        try:
            dist = pkg_resources.working_set.find(
                pkg_resources.Requirement.parse(module_path.parts[-2])
            )
            return f"{dist.key}=={dist.version}" if dist else None
        except:
            return None

    def find_module_path(self, module_name: str) -> Path:
        """Find the file path for a given module name."""
        try:
            module = importlib.import_module(module_name)
            if hasattr(module, '__file__') and module.__file__:
                module_path = Path(module.__file__).resolve()
                if self.is_venv_module(module_path):
                    package_name = self.get_package_name(module_path)
                    if package_name:
                        self.third_party_packages.add(package_name)
                return module_path
        except ImportError:
            return None

    def create_requirements_txt(self):
        """Create requirements.txt file with third-party dependencies."""
        if self.third_party_packages:
            requirements_path = self.output_path / 'requirements.txt'
            with open(requirements_path, 'w') as f:
                for package in sorted(self.third_party_packages):
                    f.write(f"{package}\n")
            print(f"\nCreated requirements.txt with {len(self.third_party_packages)} packages")

    def copy_dependencies(self):
        """Copy collected dependencies to output directory."""
        copied_count = 0
        config_count = 0
        for file_path in self.collected_files:
            if self.is_project_module(file_path) and not self.is_venv_module(file_path):
                # Calculate relative path from root
                try:
                    rel_path = file_path.relative_to(self.root_path)
                    target_path = self.output_path / rel_path

                    # Create directory structure
                    target_path.parent.mkdir(parents=True, exist_ok=True)

                    # Copy file
                    shutil.copy2(file_path, target_path)

                    # Count files by type
                    if file_path.suffix.lower() in self.config_extensions:
                        config_count += 1
                    else:
                        copied_count += 1

                    print(f"Copied: {rel_path}")
                except ValueError:
                    continue

        print(f"\nCopied {copied_count} project files and {config_count} configuration files")
        self.create_requirements_txt()

    def analyze_imports(self, file_path: Path) -> Set[str]:
        """Analyze Python file for import statements using AST."""
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())

        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    imports.add(name.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split('.')[0])
        return imports

    def is_project_module(self, module_path: Path) -> bool:
        """Check if module path is under the project root path."""
        if module_path == self.gateway_path:
            return False
        try:
            module_path.relative_to(self.root_path)
            return True
        except ValueError:
            return False

    def collect_runtime_dependencies(self, tests_path: str):
        """Collect runtime dependencies by running tests."""
        original_modules = set(sys.modules.keys())

        # Add tests directory to Python path
        sys.path.insert(0, str(Path(tests_path).parent))

        # Run pytest with capture=no to show test output
        pytest.main([tests_path, '-v'])

        # Get new modules loaded during test execution
        new_modules = set(sys.modules.keys()) - original_modules

        for module_name in new_modules:
            module = sys.modules.get(module_name)
            if module and hasattr(module, '__file__') and module.__file__:
                module_path = Path(module.__file__).resolve()
                if self.is_project_module(module_path):
                    self.collected_files.add(module_path)
                    # Add this line to collect config files from runtime dependencies
                    self.collect_config_files(module_path)

    def collect_config_files(self, module_path: Path):
        """Collect configuration files from the module's directory."""
        if not module_path.is_file():
            return

        module_dir = module_path.parent
        for file_path in module_dir.rglob('*'):
            if file_path.suffix.lower() in self.config_extensions:
                try:
                    # Check if the config file is under root_path
                    if self.is_project_module(file_path):
                        self.collected_files.add(file_path)
                        print(f"Found config file: {file_path.relative_to(self.root_path)}")
                except ValueError:
                    continue

    def collect_static_dependencies(self, file_path: Path):
        """Recursively collect static dependencies from import statements."""
        imports = self.analyze_imports(file_path)

        # Collect config files from the current module's directory
        self.collect_config_files(file_path)
        for import_name in imports:
            module_path = self.find_module_path(import_name)
            if module_path and self.is_project_module(module_path):
                if module_path not in self.collected_files:
                    self.collected_files.add(module_path)
                    # Collect config files from the imported module's directory
                    self.collect_config_files(module_path)
                    self.collect_static_dependencies(module_path)
        print()


def main():
    parser = argparse.ArgumentParser(description='Package Python script dependencies')
    parser.add_argument('gateway_path', help='Path to the gateway script')
    parser.add_argument('root_path', help='Root path of the project')
    parser.add_argument('--output-path', help='Output path for dependencies', default=None)
    parser.add_argument('--tests-path', help='Path to test files', required=True)

    args = parser.parse_args()

    collector = DependencyCollector(
        args.gateway_path,
        args.root_path,
        args.output_path
    )

    # Collect static dependencies
    print("Collecting static dependencies...")
    collector.collect_static_dependencies(collector.gateway_path)

    # Collect runtime dependencies
    print("\nCollecting runtime dependencies...")
    collector.collect_runtime_dependencies(args.tests_path)

    # Copy dependencies
    print("\nCopying dependencies...")
    collector.copy_dependencies()


if __name__ == '__main__':
    main()
