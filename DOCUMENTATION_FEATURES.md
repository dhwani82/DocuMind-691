# Documentation Generation Features

## Overview

DocuMind now includes professional documentation generation capabilities that create production-quality documentation for your Python code.

## Features

### 1. PEP 257 Compliant Docstrings

- Automatically generates docstrings for all functions and classes
- Follows Python PEP 257 conventions
- Includes:
  - Brief summary line (imperative mood)
  - Detailed descriptions
  - Args section for parameters
  - Returns section for return values
  - Raises section for exceptions (when applicable)

### 2. README.md Generation

Creates comprehensive project documentation including:
- Project title and description
- Features overview
- Installation instructions
- Usage examples
- Function/class overview
- Dependencies
- License section

### 3. ARCHITECTURE.md Generation

Generates detailed architecture documentation with:
- System overview
- Module structure
- Class hierarchy and relationships
- Function organization
- Data flow (when applicable)
- Dependencies and external libraries
- Design patterns used

## Usage Modes

### Template-Based (Default)

- Works without any API key
- Uses intelligent templates based on code structure
- Generates professional documentation automatically
- Perfect for quick documentation needs

### LLM-Enhanced (Optional)

- Requires OpenAI API key
- Uses GPT-4o-mini for context-aware documentation
- More sophisticated and comprehensive
- Better understanding of code purpose and relationships
- Enhanced descriptions and explanations

## How to Use

1. **Analyze your code** first using the "Analyze Code" button
2. **Enter OpenAI API key** (optional) in the API key field
3. **Click "Generate Documentation"** button
4. **View generated docs** in three tabs:
   - Docstrings: Code with added docstrings
   - README.md: Project documentation
   - ARCHITECTURE.md: Architecture documentation
5. **Download** any document using the download buttons
6. **Copy to clipboard** for easy pasting

## API Key Setup (Optional)

1. Get an API key from [OpenAI Platform](https://platform.openai.com/)
2. Enter it in the optional API key field
3. The key is only sent to the server for that request (not stored)
4. If no key is provided, template-based generation is used

## Output Quality

Both modes generate production-quality documentation:
- Consistent formatting
- Professional structure
- Easy onboarding for new developers
- Clear explanations
- Proper markdown formatting

## Technical Details

- **Backend**: Flask API endpoint `/api/generate-docs`
- **LLM Model**: GPT-4o-mini (when API key provided)
- **Fallback**: Template-based generation (always available)
- **Format**: Markdown for README and ARCHITECTURE, Python code for docstrings

