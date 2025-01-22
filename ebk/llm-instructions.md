Below is an example of an **`llm-instructions.md`** file. It provides guidelines to any Large Language Model (LLM) on how to map user requests (in natural language) into the corresponding `ebk` CLI commands and arguments. You can customize or expand on these instructions based on your specific integration needs.

---

# LLM Instructions for ebk

This document guides the LLM to interpret natural language requests about managing eBook libraries and transform them into the appropriate `ebk` CLI commands. The CLI uses [Typer](https://typer.tiangolo.com/) with various subcommands for importing, exporting, merging, searching, etc.

## Important Notes

1. **Be Concise**: Whenever possible, use the minimal command and arguments that fulfill the user’s request.  
2. **Validate**: Ensure that any generated command references existing subcommands and flags.  
3. **Do Not Output Explanations**: Ideally, the LLM should output only the final CLI command (unless the request specifically asks for an explanation).  
4. **Fields & Options**: If a user’s request omits necessary details, politely request clarification or provide placeholders (e.g., `/path/to/library`).

---

## Primary Subcommands Overview

Below is a short summary of each subcommand and typical usage patterns.

1. **import-zip**  
   - **Usage**: `ebk import-zip <ZIP_FILE> [--output-dir <OUTPUT_DIR>]`  
   - **Purpose**: Imports an existing ebk library archived in a `.zip` file.

2. **import-calibre**  
   - **Usage**: `ebk import-calibre <CALIBRE_DIR> [--output-dir <OUTPUT_DIR>]`  
   - **Purpose**: Convert a Calibre library folder into an ebk library.

3. **import-ebooks**  
   - **Usage**:  
     ```
     ebk import-ebooks <EBOOKS_DIR> 
       [--output-dir <OUTPUT_DIR>] 
       [--ebook-formats <FORMAT1> <FORMAT2> ...]
     ```  
   - **Purpose**: Recursively import raw ebook files (PDF, EPUB, MOBI, etc.) and generate `metadata.json`.

4. **export**  
   - **Usage**:  
     ```
     ebk export <FORMAT> <LIB_DIR> [DESTINATION]
     ```  
   - **Formats**: `zip` or `hugo`.

5. **merge**  
   - **Usage**:  
     ```
     ebk merge <OPERATION> <OUTPUT_DIR> <LIB1> <LIB2> [<LIB3>...]
     ```  
   - **Operations**: `union`, `intersect`, `diff`, `symdiff`.

6. **search**  
   - **Usage**:  
     ```
     ebk search <EXPRESSION> <LIB_DIR> 
       [--jmespath] 
       [--json] 
       [--regex-fields <FIELD1> <FIELD2> ...]
     ```  
   - **Modes**: 
     - Regex-based (default; fields default to `title`), or  
     - JMESPath (`--jmespath`).

7. **stats**  
   - **Usage**:  
     ```
     ebk stats <LIB_DIR> [--keywords <KW1> <KW2> ...]
     ```  
   - **Purpose**: Collect various library statistics (languages, subjects, top authors, etc.).

8. **list**  
   - **Usage**:  
     ```
     ebk list <LIB_DIR> [--json]
     ```
   - **Purpose**: Display or list the library contents.

9. **add**  
   - **Usage**:  
     ```
     ebk add <LIB_DIR> 
       [--json <FILE>] 
       [--title <TITLE>] 
       [--creators <CREATOR1> <CREATOR2> ...]
       [--ebooks <FILES> ...]
       [--cover <COVER>]
     ```
   - **Purpose**: Append new entry(ies) to the library, from either a JSON file or explicit CLI args.

10. **remove** / **remove-index** / **remove-id**  
    - **Usage**:
      - `ebk remove <LIB_DIR> <REGEX> [--force] [--apply-to <FIELDS>...]`
      - `ebk remove-index <LIB_DIR> <INDICES...>`
      - `ebk remove-id <LIB_DIR> <UNIQUE_ID>`
    - **Purpose**: Remove library entries based on regex, index, or unique ID.

11. **update-index** / **update-id**  
    - **Usage**:
      - `ebk update-index <LIB_DIR> <INDEX> [ARGS...]`
      - `ebk update-id <LIB_DIR> <UNIQUE_ID> [ARGS...]`
    - **Purpose**: Modify existing entries by index or unique ID.

12. **dash**  
    - **Usage**: `ebk dash [--port <PORT>]`  
    - **Purpose**: Launch the Streamlit dashboard on a specified (or default) port.

---

## Mapping User Requests to Commands

When the user’s request can be interpreted in terms of library management or metadata operations, **transform** their text into the correct subcommand and arguments. For instance:

1. **User says**: “Convert this Calibre library at `/my/calibre` into an ebk format.”  
   **Answer**:  
   ```bash
   ebk import-calibre /my/calibre --output-dir /my/calibre-ebk
   ```

2. **User says**: “I want to unify two libraries using union.”  
   **Answer**:  
   ```bash
   ebk merge union /path/to/union_output /path/to/libA /path/to/libB
   ```

3. **User says**: “Search for all ebooks with ‘Python’ in the title.”  
   **Answer**:  
   ```bash
   ebk search "Python" /path/to/lib --regex-fields title
   ```

4. **User says**: “Show me stats for my library at `/data/my_ebooks`.”  
   **Answer**:  
   ```bash
   ebk stats /data/my_ebooks
   ```

5. **User says**: “Add a new entry called ‘Cool Book’ by ‘Jane Doe’ with a PDF file at `/books/cool-book.pdf`.”  
   **Answer**:  
   ```bash
   ebk add /path/to/lib \
     --title "Cool Book" \
     --creators "Jane Doe" \
     --ebooks "/books/cool-book.pdf"
   ```

---

## Handling Ambiguities or Missing Details

- If the user’s query lacks a required path (e.g., library path) or subcommand details, you may:
  1. Ask clarifying questions: “Which library path should I use?”  
  2. Provide a placeholder: e.g., `/path/to/lib`.

- If the user requests a feature not supported (e.g., “Fully transform all eBooks to .mobi”), politely note that **ebk** doesn’t handle that conversion.

---

## Example Prompt / Response Format

- **Prompt** (User request in natural language):
  ```
  I need to import a zip file at '/archives/my_ebk.zip' into a new ebk library, maybe in '/home/user/my_library'. 
  ```

- **LLM Output** (CLI command only):
  ```
  ebk import-zip /archives/my_ebk.zip --output-dir /home/user/my_library
  ```

**End**  

This is the expected pattern: read the user’s text → produce the best matching `ebk` command. Avoid extra commentary unless requested.

---

## Summary

By following these guidelines, any LLM can be primed to interpret user input as instructions for `ebk`. Keep the outputs **focused**, **accurate**, and **aligned** with the subcommands listed.