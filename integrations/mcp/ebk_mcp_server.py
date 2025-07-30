#!/usr/bin/env python3
"""
ebk MCP Server

This MCP server provides tools for AI assistants to interact with ebk libraries.
It exposes the core functionality of ebk through a standardized protocol.
"""

import os
import sys
import json
import subprocess
from typing import Dict, List, Any, Optional
from pathlib import Path

from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types


class EbkMCPServer:
    def __init__(self):
        self.server = Server("ebk")
        self._setup_tools()
        
    def _setup_tools(self):
        """Register all ebk tools with the MCP server"""
        
        # Import tools
        @self.server.tool()
        async def import_calibre(
            calibre_dir: str,
            output_dir: Optional[str] = None
        ) -> Dict[str, Any]:
            """Import a Calibre library into ebk format"""
            cmd = ["ebk", "import-calibre", calibre_dir]
            if output_dir:
                cmd.extend(["--output-dir", output_dir])
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr
            }
        
        @self.server.tool()
        async def import_ebooks(
            ebooks_dir: str,
            output_dir: Optional[str] = None,
            formats: Optional[List[str]] = None
        ) -> Dict[str, Any]:
            """Import a directory of ebooks"""
            cmd = ["ebk", "import-ebooks", ebooks_dir]
            if output_dir:
                cmd.extend(["--output-dir", output_dir])
            if formats:
                for fmt in formats:
                    cmd.extend(["--ebook-formats", fmt])
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr
            }
        
        @self.server.tool()
        async def import_zip(
            zip_file: str,
            output_dir: Optional[str] = None
        ) -> Dict[str, Any]:
            """Import an ebk library from a ZIP file"""
            cmd = ["ebk", "import-zip", zip_file]
            if output_dir:
                cmd.extend(["--output-dir", output_dir])
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr
            }
        
        # Export tools
        @self.server.tool()
        async def export_zip(
            lib_dir: str,
            destination: Optional[str] = None
        ) -> Dict[str, Any]:
            """Export library to ZIP format"""
            cmd = ["ebk", "export", "zip", lib_dir]
            if destination:
                cmd.append(destination)
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr
            }
        
        @self.server.tool()
        async def export_hugo(
            lib_dir: str,
            destination: str
        ) -> Dict[str, Any]:
            """Export library for Hugo static site"""
            cmd = ["ebk", "export", "hugo", lib_dir, destination]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr
            }
        
        # Search and list tools
        @self.server.tool()
        async def list_library(
            lib_dir: str,
            output_json: bool = False
        ) -> Dict[str, Any]:
            """List all entries in a library"""
            cmd = ["ebk", "list", lib_dir]
            if output_json:
                cmd.append("--json")
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if output_json and result.returncode == 0:
                try:
                    entries = json.loads(result.stdout)
                    return {
                        "success": True,
                        "entries": entries,
                        "count": len(entries)
                    }
                except json.JSONDecodeError:
                    pass
            
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr
            }
        
        @self.server.tool()
        async def search(
            lib_dir: str,
            pattern: str,
            regex_fields: Optional[List[str]] = None,
            use_jmespath: bool = False,
            output_json: bool = False
        ) -> Dict[str, Any]:
            """Search library using regex or JMESPath"""
            cmd = ["ebk", "search", pattern, lib_dir]
            
            if use_jmespath:
                cmd.append("--jmespath")
            elif regex_fields:
                for field in regex_fields:
                    cmd.extend(["--regex-fields", field])
                    
            if output_json:
                cmd.append("--json")
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if output_json and result.returncode == 0:
                try:
                    entries = json.loads(result.stdout)
                    return {
                        "success": True,
                        "entries": entries,
                        "count": len(entries)
                    }
                except json.JSONDecodeError:
                    pass
            
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr
            }
        
        @self.server.tool()
        async def stats(
            lib_dir: str,
            keywords: Optional[List[str]] = None
        ) -> Dict[str, Any]:
            """Get library statistics"""
            cmd = ["ebk", "stats", lib_dir]
            if keywords:
                for kw in keywords:
                    cmd.extend(["--keywords", kw])
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                try:
                    stats = json.loads(result.stdout)
                    return {
                        "success": True,
                        "stats": stats
                    }
                except json.JSONDecodeError:
                    pass
            
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr
            }
        
        # Entry management tools
        @self.server.tool()
        async def add_entry(
            lib_dir: str,
            title: Optional[str] = None,
            creators: Optional[List[str]] = None,
            ebooks: Optional[List[str]] = None,
            cover: Optional[str] = None,
            json_file: Optional[str] = None
        ) -> Dict[str, Any]:
            """Add new entry to library"""
            cmd = ["ebk", "add", lib_dir]
            
            if json_file:
                cmd.extend(["--json", json_file])
            else:
                if title:
                    cmd.extend(["--title", title])
                if creators:
                    for creator in creators:
                        cmd.extend(["--creators", creator])
                if ebooks:
                    for ebook in ebooks:
                        cmd.extend(["--ebooks", ebook])
                if cover:
                    cmd.extend(["--cover", cover])
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr
            }
        
        @self.server.tool()
        async def remove_by_regex(
            lib_dir: str,
            regex: str,
            force: bool = False,
            apply_to: Optional[List[str]] = None
        ) -> Dict[str, Any]:
            """Remove entries matching regex pattern"""
            cmd = ["ebk", "remove", lib_dir, regex]
            
            if force:
                cmd.append("--force")
            if apply_to:
                for field in apply_to:
                    cmd.extend(["--apply-to", field])
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr
            }
        
        @self.server.tool()
        async def merge_libraries(
            operation: str,
            output_dir: str,
            libraries: List[str]
        ) -> Dict[str, Any]:
            """Merge multiple libraries using set operations (union, intersect, diff, symdiff)"""
            cmd = ["ebk", "merge", operation, output_dir] + libraries
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr
            }
        
    async def run(self):
        """Run the MCP server"""
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="ebk",
                    server_version="0.1.0",
                    capabilities=self.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )


def main():
    """Main entry point"""
    import asyncio
    
    server = EbkMCPServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()