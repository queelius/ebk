import argparse
import subprocess

def main():
    parser = argparse.ArgumentParser(description="eBook Library Manager CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Convert command
    convert_parser = subparsers.add_parser("convert", help="Convert Calibre library to JSON")
    convert_parser.add_argument("source", help="Path to the Calibre library folder")
    convert_parser.add_argument("output", help="Path to the output JSON file")

    # Export command
    export_parser = subparsers.add_parser("export", help="Export JSON library to Hugo")
    export_parser.add_argument("json_file", help="Path to the JSON file")
    export_parser.add_argument("hugo_dir", help="Path to the Hugo site directory")

    # App command
    app_parser = subparsers.add_parser("dash", help="Launch the Streamlit dashboard")
    app_parser.add_argument("--port", default=8501, type=int, help="Port to run the Streamlit app (default: 8501)")

    args = parser.parse_args()

    if args.command == "convert":
        from ebk.convert_calibre import convert_calibre_to_json
        convert_calibre_to_json(args.source, args.output)
    elif args.command == "export":
        from exporter import export_to_hugo
        export_to_hugo(args.json_file, args.hugo_dir)
    elif args.command == "app":
        launch_streamlit_app(args.port)
    else:
        parser.print_help()

def launch_streamlit_app(port):
    """Launch the Streamlit app."""
    try:
        print(f"Starting Streamlit app on port {port}...")
        subprocess.run(["streamlit", "run", "dash.py", "--server.port", str(port)])
    except FileNotFoundError:
        print("Error: Streamlit is not installed. Please install it with `pip install streamlit`.")

if __name__ == "__main__":
    main()
