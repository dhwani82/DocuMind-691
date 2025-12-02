let currentView = 'summary';
let currentData = null;
let currentCode = '';
let currentDocumentation = null;

function switchTab(tab) {
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
    
    if (tab === 'paste') {
        document.querySelector('.tab-btn').classList.add('active');
        document.getElementById('paste-tab').classList.add('active');
    } else {
        document.querySelectorAll('.tab-btn')[1].classList.add('active');
        document.getElementById('upload-tab').classList.add('active');
    }
}

// File upload handling
const uploadArea = document.getElementById('upload-area');
const fileInput = document.getElementById('file-input');

uploadArea.addEventListener('click', () => fileInput.click());

uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.classList.add('dragover');
});

uploadArea.addEventListener('dragleave', () => {
    uploadArea.classList.remove('dragover');
});

uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        handleFile(files[0]);
    }
});

fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        handleFile(e.target.files[0]);
    }
});

function handleFile(file) {
    if (!file.name.endsWith('.py')) {
        showError('Please upload a Python (.py) file');
        return;
    }
    
    const reader = new FileReader();
    reader.onload = (e) => {
        document.getElementById('code-input').value = e.target.result;
        currentCode = e.target.result;
        switchTab('paste');
    };
    reader.readAsText(file);
}

async function parseCode() {
    const code = document.getElementById('code-input').value.trim();
    
    if (!code) {
        showError('Please enter or upload some Python code');
        return;
    }
    
    currentCode = code;
    hideError();
    showLoading();
    
    try {
        const response = await fetch('/api/parse', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ code: code })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            showError(data.error || 'An error occurred');
            return;
        }
        
        currentData = data;
        displayResults(data);
        
        // Show documentation button after successful parse
        document.getElementById('doc-btn').style.display = 'block';
        
        // Display diagrams if available
        if (data.diagrams) {
            displayDiagrams(data.diagrams);
        }
        
    } catch (error) {
        showError('Network error: ' + error.message);
    }
}

function toggleProviderSettings() {
    const provider = document.getElementById('provider-select').value;
    const openaiSettings = document.getElementById('openai-settings');
    const ollamaSettings = document.getElementById('ollama-settings');
    
    if (provider === 'openai') {
        openaiSettings.style.display = 'block';
        ollamaSettings.style.display = 'none';
    } else if (provider === 'ollama') {
        openaiSettings.style.display = 'none';
        ollamaSettings.style.display = 'block';
    } else {
        openaiSettings.style.display = 'none';
        ollamaSettings.style.display = 'none';
    }
}

async function generateDocumentation() {
    if (!currentCode) {
        showError('Please analyze code first');
        return;
    }
    
    const provider = document.getElementById('provider-select').value;
    const apiKey = document.getElementById('api-key-input').value.trim();
    const ollamaModel = document.getElementById('ollama-model-input')?.value.trim() || 'llama2';
    const ollamaBaseUrl = document.getElementById('ollama-url-input')?.value.trim() || 'http://localhost:11434';
    
    hideError();
    
    // Show loading state
    const docBtn = document.getElementById('doc-btn');
    const originalText = docBtn.querySelector('span').textContent;
    docBtn.querySelector('span').textContent = 'Generating...';
    docBtn.disabled = true;
    
    try {
        const requestBody = {
            code: currentCode,
            provider: provider
        };
        
        if (provider === 'openai') {
            requestBody.api_key = apiKey || null;
        } else if (provider === 'ollama') {
            requestBody.ollama_model = ollamaModel;
            requestBody.ollama_base_url = ollamaBaseUrl;
        }
        // For 'template', no additional fields needed - backend will handle it
        
        const response = await fetch('/api/generate-docs', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestBody)
        });
        
        // Check if response is JSON
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            const text = await response.text();
            console.error('Non-JSON response:', text.substring(0, 200));
            showError('Server returned an error. Please check the server logs. The server may need to be restarted.');
            return;
        }
        
        const data = await response.json();
        
        if (!response.ok) {
            showError(data.error || 'An error occurred while generating documentation');
            return;
        }
        
        currentDocumentation = data.documentation;
        displayDocumentation(data.documentation, data.used_llm);
        
        // Scroll to documentation section
        document.getElementById('documentation-section').scrollIntoView({ behavior: 'smooth' });
        
    } catch (error) {
        console.error('Error details:', error);
        if (error.message.includes('JSON')) {
            showError('Server error: The server returned an HTML error page instead of JSON. Please check if the server is running and restart it if needed.');
        } else {
            showError('Network error: ' + error.message);
        }
    } finally {
        docBtn.querySelector('span').textContent = originalText;
        docBtn.disabled = false;
    }
}

function displayDocumentation(docs, usedLLM) {
    const docSection = document.getElementById('documentation-section');
    docSection.style.display = 'block';
    
    // Display docstrings
    const docstringsContent = document.getElementById('docstrings-content');
    docstringsContent.textContent = docs.docstrings;
    
    // Display README (convert markdown to HTML)
    const readmeContent = document.getElementById('readme-content');
    readmeContent.innerHTML = convertMarkdownToHTML(docs.readme);
    
    // Display ARCHITECTURE
    const archContent = document.getElementById('architecture-content');
    archContent.innerHTML = convertMarkdownToHTML(docs.architecture);
    
    // Show info about LLM usage
    if (usedLLM) {
        const info = document.createElement('div');
        info.className = 'info-message';
        info.style.cssText = 'background: #e6f3ff; color: #0066cc; padding: 10px; border-radius: 6px; margin-bottom: 15px;';
        info.textContent = '✓ Documentation generated using AI (LLM)';
        docSection.insertBefore(info, docSection.firstChild);
    } else {
        const info = document.createElement('div');
        info.className = 'info-message';
        info.style.cssText = 'background: #fff3cd; color: #856404; padding: 10px; border-radius: 6px; margin-bottom: 15px;';
        info.textContent = 'ℹ Using template-based documentation. Add OpenAI API key for enhanced AI-generated docs.';
        docSection.insertBefore(info, docSection.firstChild);
    }
}

function switchDocTab(tab) {
    // Hide all tabs
    document.querySelectorAll('.doc-content').forEach(content => {
        content.classList.remove('active');
    });
    document.querySelectorAll('.doc-tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Show selected tab
    document.getElementById(`${tab}-view`).classList.add('active');
    event.target.classList.add('active');
}

function downloadDoc(type) {
    if (!currentDocumentation) return;
    
    let content, filename, mimeType;
    
    switch(type) {
        case 'docstrings':
            content = currentDocumentation.docstrings;
            filename = 'code_with_docstrings.py';
            mimeType = 'text/python';
            break;
        case 'readme':
            content = currentDocumentation.readme;
            filename = 'README.md';
            mimeType = 'text/markdown';
            break;
        case 'architecture':
            content = currentDocumentation.architecture;
            filename = 'ARCHITECTURE.md';
            mimeType = 'text/markdown';
            break;
        default:
            return;
    }
    
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

function copyDoc(type) {
    if (!currentDocumentation) return;
    
    let content;
    switch(type) {
        case 'docstrings':
            content = currentDocumentation.docstrings;
            break;
        case 'readme':
            content = currentDocumentation.readme;
            break;
        case 'architecture':
            content = currentDocumentation.architecture;
            break;
        default:
            return;
    }
    
    navigator.clipboard.writeText(content).then(() => {
        const btn = event.target.closest('.action-btn');
        const originalText = btn.textContent;
        btn.textContent = 'Copied!';
        setTimeout(() => {
            btn.textContent = originalText;
        }, 2000);
    });
}

function convertMarkdownToHTML(markdown) {
    // Simple markdown to HTML converter
    let html = markdown;
    
    // Headers
    html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
    html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
    html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');
    
    // Code blocks
    html = html.replace(/```(\w+)?\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>');
    
    // Inline code
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    
    // Bold
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    
    // Italic
    html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
    
    // Lists
    html = html.replace(/^\* (.*$)/gim, '<li>$1</li>');
    html = html.replace(/^- (.*$)/gim, '<li>$1</li>');
    html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');
    
    // Links
    html = html.replace(/\[([^\]]+)\]\(([^\)]+)\)/g, '<a href="$2">$1</a>');
    
    // Line breaks
    html = html.replace(/\n\n/g, '</p><p>');
    html = '<p>' + html + '</p>';
    
    // Clean up empty paragraphs
    html = html.replace(/<p><\/p>/g, '');
    html = html.replace(/<p>(<[^>]+>)/g, '$1');
    html = html.replace(/(<\/[^>]+>)<\/p>/g, '$1');
    
    return html;
}

function showLoading() {
    const outputSection = document.getElementById('output-section');
    outputSection.style.display = 'block';
    outputSection.innerHTML = '<div class="loading">Analyzing code</div>';
}

function displayResults(data) {
    const outputSection = document.getElementById('output-section');
    outputSection.style.display = 'block';
    outputSection.innerHTML = `
        <div class="output-header">
            <h2>Analysis Results</h2>
            <div class="output-actions">
                <button class="action-btn" onclick="toggleView()">
                    <span id="view-toggle">View JSON</span>
                </button>
                <button class="action-btn" onclick="copyToClipboard()">
                    <span>Copy JSON</span>
                </button>
            </div>
        </div>
        <div id="summary-view" class="summary-view"></div>
        <div id="json-view" class="json-view" style="display: none;">
            <pre id="json-output"></pre>
        </div>
    `;
    
    displaySummary(data);
    displayJSON(data);
    currentView = 'summary';
}

function displaySummary(data) {
    const summaryView = document.getElementById('summary-view');
    const summary = data.summary;
    
    summaryView.innerHTML = `
        <div class="stat-card">
            <h3>Total Functions</h3>
            <div class="value">${summary.total_functions}</div>
            <div style="margin-top: 10px; font-size: 0.85rem; color: #666;">
                ${summary.sync_functions} sync, ${summary.async_functions} async, ${summary.nested_functions} nested
            </div>
        </div>
        <div class="stat-card">
            <h3>Classes</h3>
            <div class="value">${summary.total_classes}</div>
        </div>
        <div class="stat-card">
            <h3>Methods</h3>
            <div class="value">${summary.total_methods}</div>
        </div>
        <div class="stat-card">
            <h3>Global Variables</h3>
            <div class="value">${summary.global_variables}</div>
        </div>
        <div class="stat-card">
            <h3>Local Variables</h3>
            <div class="value">${summary.local_variables || 0}</div>
        </div>
        <div class="stat-card">
            <h3>Class Variables</h3>
            <div class="value">${summary.class_variables}</div>
        </div>
        <div class="stat-card">
            <h3>Instance Variables</h3>
            <div class="value">${summary.instance_variables}</div>
        </div>
        <div class="stat-card">
            <h3>Decorators</h3>
            <div class="value">${summary.total_decorators}</div>
        </div>
        <div class="stat-card">
            <h3>Imports</h3>
            <div class="value">${summary.total_imports}</div>
        </div>
    `;
    
    // Add detailed sections
    if (data.functions && data.functions.length > 0) {
        summaryView.innerHTML += createDetailSection('Functions', data.functions, (f) => {
            const type = f.is_async ? 'async' : 'sync';
            const nested = f.is_nested ? 'nested' : 'top-level';
            return `
                <div class="detail-item">
                    <div class="name">${f.name}</div>
                    <div class="meta">
                        <span>Line: ${f.line}</span>
                        <span>Type: ${type}</span>
                        <span>${nested}</span>
                        ${f.decorators.length > 0 ? `<span>Decorators: ${f.decorators.join(', ')}</span>` : ''}
                        ${f.parameters.length > 0 ? `<span>Params: ${f.parameters.join(', ')}</span>` : ''}
                        ${f.returns ? `<span>Returns: ${f.returns}</span>` : ''}
                    </div>
                </div>
            `;
        });
    }
    
    if (data.classes && data.classes.length > 0) {
        summaryView.innerHTML += createDetailSection('Classes', data.classes, (c) => {
            return `
                <div class="detail-item">
                    <div class="name">${c.name}</div>
                    <div class="meta">
                        <span>Line: ${c.line}</span>
                        ${c.bases.length > 0 ? `<span>Bases: ${c.bases.join(', ')}</span>` : ''}
                        ${c.decorators.length > 0 ? `<span>Decorators: ${c.decorators.join(', ')}</span>` : ''}
                        <span>Methods: ${c.methods.length}</span>
                        <span>Class vars: ${c.class_variables.length}</span>
                        <span>Instance vars: ${c.instance_variables.length}</span>
                    </div>
                </div>
            `;
        });
    }
    
    if (data.global_variables && data.global_variables.length > 0) {
        summaryView.innerHTML += createDetailSection('Global Variables', data.global_variables, (v) => {
            return `
                <div class="detail-item">
                    <div class="name">${v.name}</div>
                    <div class="meta">
                        <span>Line: ${v.line}</span>
                        ${v.type && v.type !== 'unknown' ? `<span>Type: ${v.type}</span>` : ''}
                    </div>
                </div>
            `;
        });
    }
    
    if (data.local_variables && data.local_variables.length > 0) {
        // Group local variables by function
        const varsByFunction = {};
        data.local_variables.forEach(v => {
            const funcName = v.function;
            if (!varsByFunction[funcName]) {
                varsByFunction[funcName] = [];
            }
            varsByFunction[funcName].push(v);
        });
        
        // Display grouped by function
        Object.keys(varsByFunction).forEach(funcName => {
            const funcVars = varsByFunction[funcName];
            const isMethod = funcVars[0].is_method;
            const sectionTitle = isMethod ? `Local Variables in ${funcName}` : `Local Variables in ${funcName}()`;
            
            summaryView.innerHTML += createDetailSection(sectionTitle, funcVars, (v) => {
                return `
                    <div class="detail-item">
                        <div class="name">${v.name}</div>
                        <div class="meta">
                            <span>Line: ${v.line}</span>
                            ${v.type && v.type !== 'unknown' ? `<span>Type: ${v.type}</span>` : ''}
                        </div>
                    </div>
                `;
            });
        });
    }
    
    if (data.imports && data.imports.length > 0) {
        summaryView.innerHTML += createDetailSection('Imports', data.imports, (imp) => {
            if (imp.type === 'from_import') {
                return `
                    <div class="detail-item">
                        <div class="name">from ${imp.module} import ${imp.name}${imp.alias ? ` as ${imp.alias}` : ''}</div>
                        <div class="meta"><span>Line: ${imp.line}</span></div>
                    </div>
                `;
            } else {
                return `
                    <div class="detail-item">
                        <div class="name">import ${imp.module}${imp.alias ? ` as ${imp.alias}` : ''}</div>
                        <div class="meta"><span>Line: ${imp.line}</span></div>
                    </div>
                `;
            }
        });
    }
    
    if (data.decorators && data.decorators.length > 0) {
        summaryView.innerHTML += createDetailSection('Decorators', data.decorators, (d) => {
            return `
                <div class="detail-item">
                    <div class="name">${d.name}</div>
                    <div class="meta">${d.line ? `<span>Line: ${d.line}</span>` : ''}</div>
                </div>
            `;
        });
    }
}

function createDetailSection(title, items, itemRenderer) {
    if (items.length === 0) return '';
    
    return `
        <div class="detail-section">
            <h3>${title} (${items.length})</h3>
            ${items.map(itemRenderer).join('')}
        </div>
    `;
}

function displayJSON(data) {
    const jsonView = document.getElementById('json-output');
    jsonView.textContent = JSON.stringify(data, null, 2);
}

function toggleView() {
    const summaryView = document.getElementById('summary-view');
    const jsonView = document.getElementById('json-view');
    const toggleBtn = document.getElementById('view-toggle');
    
    if (currentView === 'summary') {
        summaryView.style.display = 'none';
        jsonView.style.display = 'block';
        toggleBtn.textContent = 'View Summary';
        currentView = 'json';
    } else {
        summaryView.style.display = 'block';
        jsonView.style.display = 'none';
        toggleBtn.textContent = 'View JSON';
        currentView = 'summary';
    }
}

function copyToClipboard() {
    if (!currentData) return;
    
    const jsonString = JSON.stringify(currentData, null, 2);
    navigator.clipboard.writeText(jsonString).then(() => {
        const btn = event.target.closest('.action-btn');
        const originalText = btn.querySelector('span').textContent;
        btn.querySelector('span').textContent = 'Copied!';
        setTimeout(() => {
            btn.querySelector('span').textContent = originalText;
        }, 2000);
    });
}

function showError(message) {
    const errorDiv = document.getElementById('error-message');
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';
}

function hideError() {
    document.getElementById('error-message').style.display = 'none';
}

function displayDiagrams(diagrams) {
    const diagramsSection = document.getElementById('diagrams-section');
    if (!diagramsSection) return;
    
    diagramsSection.style.display = 'block';
    
    // Wait for Mermaid to be available
    const renderDiagram = (elementId, diagramCode) => {
        const element = document.getElementById(elementId);
        if (!element || !diagramCode) return;
        
        // Clean the diagram code
        let cleanCode = diagramCode.replace(/```mermaid\n?/g, '').replace(/```\n?/g, '').trim();
        
        // Check if Mermaid is loaded
        if (typeof mermaid === 'undefined') {
            element.innerHTML = '<p style="color: #c33;">Mermaid.js library is loading. Please refresh the page.</p>';
            return;
        }
        
        // Initialize Mermaid if not already done
        if (!window.mermaidInitialized) {
            try {
                mermaid.initialize({ 
                    startOnLoad: false,
                    theme: 'default',
                    flowchart: { useMaxWidth: true },
                    sequence: { diagramMarginX: 50, diagramMarginY: 10 }
                });
                window.mermaidInitialized = true;
            } catch (err) {
                console.error('Error initializing Mermaid:', err);
            }
        }
        
        // Set the diagram code
        element.textContent = cleanCode;
        
        // Render the diagram
        try {
            mermaid.run({ 
                nodes: [element],
                suppressErrors: true
            }).catch(err => {
                console.error(`Error rendering ${elementId}:`, err);
                element.innerHTML = `<p style="color: #c33; padding: 20px;">Error rendering diagram. Diagram code:<br><pre style="font-size: 0.8em; overflow: auto;">${cleanCode.substring(0, 500)}</pre></p>`;
            });
        } catch (err) {
            console.error(`Error rendering ${elementId}:`, err);
            element.innerHTML = `<p style="color: #c33;">Error rendering diagram.</p>`;
        }
    };
    
    // Render all diagrams
    renderDiagram('architecture-mermaid', diagrams.architecture);
    renderDiagram('sequence-mermaid', diagrams.sequence);
    renderDiagram('dependencies-mermaid', diagrams.dependencies);
    renderDiagram('flowchart-mermaid', diagrams.flowchart);
    renderDiagram('structure-mermaid', diagrams.structure);
}

function switchDiagramTab(tab) {
    // Hide all tabs
    document.querySelectorAll('.diagram-content').forEach(content => {
        content.classList.remove('active');
    });
    document.querySelectorAll('.diagram-tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Show selected tab
    document.getElementById(`${tab}-diagram`).classList.add('active');
    event.target.classList.add('active');
}

async function downloadSVGFlowchart() {
    if (!currentCode) {
        showError('Please analyze code first');
        return;
    }
    
    try {
        const response = await fetch('/api/generate-svg-flowchart', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                code: currentCode,
                function_name: null  // Can be set to specific function name
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            showError(error.error || 'Error generating SVG');
            return;
        }
        
        // Get SVG content
        const svgBlob = await response.blob();
        const url = URL.createObjectURL(svgBlob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'flowchart.svg';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
    } catch (error) {
        showError('Network error: ' + error.message);
    }
}

