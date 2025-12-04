let currentView = 'summary';
let currentData = null;
let currentCode = '';
let currentDocumentation = null;
let varSectionCounter = 0;
let currentFilename = null; // Store current filename for language detection
let currentParserMode = 'single'; // 'single' or 'project'
let currentProjectFileDetails = null; // Store project file details for filtering

function switchParserMode(mode) {
    currentParserMode = mode;
    const singleFileMode = document.getElementById('single-file-mode');
    const projectMode = document.getElementById('project-mode');
    
    if (mode === 'single') {
        singleFileMode.style.display = 'block';
        projectMode.style.display = 'none';
    } else {
        singleFileMode.style.display = 'none';
        projectMode.style.display = 'block';
    }
}

function switchProjectTab(tab) {
    const pathTab = document.getElementById('project-path-tab');
    const uploadTab = document.getElementById('project-upload-tab');
    const githubTab = document.getElementById('project-github-tab');
    const tabButtons = document.querySelectorAll('#project-mode .tab-btn');
    
    tabButtons.forEach(btn => btn.classList.remove('active'));
    
    // Hide all tabs
    pathTab.classList.remove('active');
    uploadTab.classList.remove('active');
    if (githubTab) githubTab.classList.remove('active');
    
    if (tab === 'path') {
        pathTab.classList.add('active');
        tabButtons[0].classList.add('active');
    } else if (tab === 'upload') {
        uploadTab.classList.add('active');
        tabButtons[1].classList.add('active');
    } else if (tab === 'github') {
        if (githubTab) githubTab.classList.add('active');
        tabButtons[2].classList.add('active');
    }
}

let selectedProjectFiles = [];

function enableFolderUpload() {
    const fileInput = document.getElementById('project-file-input');
    // Enable folder selection
    fileInput.setAttribute('webkitdirectory', '');
    fileInput.setAttribute('directory', '');
    fileInput.setAttribute('multiple', '');
    fileInput.click();
    // Reset after selection to allow switching between file and folder modes
    fileInput.addEventListener('change', function(e) {
        handleProjectFileSelection(e);
        // Reset attributes after handling
        setTimeout(() => {
            fileInput.removeAttribute('webkitdirectory');
            fileInput.removeAttribute('directory');
        }, 100);
    }, { once: true });
}

// Initialize file input handler
document.addEventListener('DOMContentLoaded', function() {
    const projectFileInput = document.getElementById('project-file-input');
    if (projectFileInput) {
        // Don't add change listener here - it's handled in enableFolderUpload and the click handler
        
        // Enable drag and drop
        const uploadArea = document.getElementById('project-upload-area');
        if (uploadArea) {
            uploadArea.addEventListener('dragover', (e) => {
                e.preventDefault();
                uploadArea.style.borderColor = '#3b82f6';
                uploadArea.style.background = 'rgba(59, 130, 246, 0.1)';
            });
            
            uploadArea.addEventListener('dragleave', (e) => {
                e.preventDefault();
                uploadArea.style.borderColor = '#475569';
                uploadArea.style.background = '';
            });
            
            uploadArea.addEventListener('drop', (e) => {
                e.preventDefault();
                uploadArea.style.borderColor = '#475569';
                uploadArea.style.background = '';
                
                const files = Array.from(e.dataTransfer.files);
                handleProjectFiles(files);
            });
            
            uploadArea.addEventListener('click', (e) => {
                if (e.target === uploadArea || e.target.closest('.upload-placeholder')) {
                    // Ensure multiple files is enabled but not folder mode
                    projectFileInput.removeAttribute('webkitdirectory');
                    projectFileInput.removeAttribute('directory');
                    projectFileInput.setAttribute('multiple', '');
                    projectFileInput.click();
                }
            });
            
            // Add change listener for regular file selection
            projectFileInput.addEventListener('change', function(e) {
                if (!projectFileInput.hasAttribute('webkitdirectory')) {
                    handleProjectFileSelection(e);
                }
            });
        }
    }
});

function handleProjectFileSelection(event) {
    const files = Array.from(event.target.files);
    handleProjectFiles(files);
}

function handleProjectFiles(files) {
    // Filter only supported file types
    const supportedExtensions = ['.py', '.pyw', '.pyi', '.js', '.jsx', '.mjs', '.java', 
                                 '.c', '.cpp', '.cc', '.cxx', '.h', '.hpp', '.hxx', 
                                 '.php', '.phtml', '.sql'];
    
    selectedProjectFiles = files.filter(file => {
        const ext = '.' + file.name.split('.').pop().toLowerCase();
        return supportedExtensions.includes(ext);
    });
    
    if (selectedProjectFiles.length === 0) {
        showError('No supported files found. Please select files with supported extensions.');
        return;
    }
    
    // Display file list
    displayProjectFileList(selectedProjectFiles);
}

function displayProjectFileList(files) {
    const fileListDiv = document.getElementById('project-file-list');
    const fileListContent = document.getElementById('project-file-list-content');
    const uploadPlaceholder = document.querySelector('#project-upload-area .upload-placeholder');
    
    if (!fileListDiv || !fileListContent) return;
    
    fileListContent.innerHTML = '';
    
    files.forEach((file, index) => {
        const fileItem = document.createElement('div');
        fileItem.style.cssText = 'padding: 10px; margin: 5px 0; background: rgba(30, 41, 59, 0.5); border-radius: 6px; display: flex; align-items: center; justify-content: space-between;';
        fileItem.innerHTML = `
            <span style="color: #e2e8f0; font-family: "Fira Code", monospace; font-size: 0.9rem;">${file.webkitRelativePath || file.name}</span>
            <span style="color: #94a3b8; font-size: 0.85rem;">${(file.size / 1024).toFixed(2)} KB</span>
        `;
        fileListContent.appendChild(fileItem);
    });
    
    fileListDiv.style.display = 'block';
    if (uploadPlaceholder) {
        uploadPlaceholder.style.display = 'none';
    }
}

async function parseUploadedProject() {
    if (selectedProjectFiles.length === 0) {
        showError('Please select files to upload');
        return;
    }
    
    hideError();
    showLoading();
    
    try {
        const formData = new FormData();
        selectedProjectFiles.forEach(file => {
            formData.append('files', file);
        });
        
        const response = await fetch('/api/parse-uploaded-project', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            showError(data.error || 'An error occurred while parsing the uploaded files');
            return;
        }
        
        currentData = data;
        
        // Log detected language if available
        if (data.language) {
            console.log(`Detected language: ${data.language}`);
        }
        
        // Show info messages
        if (data.info_messages && data.info_messages.length > 0) {
            data.info_messages.forEach(msg => {
                if (msg.type === 'info') {
                    showInfo(msg.message);
                }
            });
        }
        
        displayResults(data);
        
        // Show documentation button after successful parse
        document.getElementById('doc-btn').style.display = 'block';
        
        // Display diagrams if available
        if (data.diagrams) {
            displayDiagrams(data.diagrams);
        }
        
    } catch (error) {
        showError('Network error: ' + error.message);
    } finally {
        hideLoading();
    }
}

function validateGitHubURL(url) {
    // GitHub URL patterns:
    // https://github.com/username/repo
    // https://github.com/username/repo.git
    // git@github.com:username/repo.git
    // github.com/username/repo
    
    if (!url || !url.trim()) {
        return { valid: false, error: 'URL cannot be empty' };
    }
    
    url = url.trim();
    
    // Remove trailing .git if present
    url = url.replace(/\.git$/, '');
    
    // Handle git@github.com:username/repo format
    if (url.startsWith('git@github.com:')) {
        url = url.replace('git@github.com:', 'https://github.com/');
    }
    
    // Handle github.com/username/repo format (add https://)
    if (url.startsWith('github.com/')) {
        url = 'https://' + url;
    }
    
    // Validate GitHub URL pattern
    const githubPattern = /^https?:\/\/(www\.)?github\.com\/[\w\.-]+\/[\w\.-]+(\/)?$/;
    
    if (!githubPattern.test(url)) {
        return { valid: false, error: 'Invalid GitHub URL format. Expected: https://github.com/username/repo' };
    }
    
    // Extract username and repo name
    const match = url.match(/github\.com\/([\w\.-]+)\/([\w\.-]+)/);
    if (!match) {
        return { valid: false, error: 'Could not extract repository information from URL' };
    }
    
    return {
        valid: true,
        url: url,
        username: match[1],
        repo: match[2],
        fullName: `${match[1]}/${match[2]}`
    };
}

async function cloneAndParseRepo() {
    const repoUrl = document.getElementById('github-repo-input').value.trim();
    const infoDiv = document.getElementById('github-repo-info');
    const infoContent = document.getElementById('github-repo-info-content');
    
    // Hide previous info
    if (infoDiv) {
        infoDiv.style.display = 'none';
    }
    
    // Validate URL
    const validation = validateGitHubURL(repoUrl);
    
    if (!validation.valid) {
        showError(validation.error || 'Invalid GitHub repository URL');
        return;
    }
    
    hideError();
    showLoading();
    
    try {
        // Send request to backend to clone and parse the repository
        const response = await fetch('/api/parse-github-repo', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                repo_url: repoUrl
            })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            showError(data.error || 'An error occurred while cloning and parsing the repository');
            return;
        }
        
        currentData = data;
        
        // Log detected language if available
        if (data.language) {
            console.log(`Detected language: ${data.language}`);
        }
        
        // Show info messages
        if (data.info_messages && data.info_messages.length > 0) {
            data.info_messages.forEach(msg => {
                if (msg.type === 'info') {
                    showInfo(msg.message);
                }
            });
        }
        
        // Display results (same as local folder mode)
        displayResults(data);
        
        // Show documentation button after successful parse
        document.getElementById('doc-btn').style.display = 'block';
        
        // Display diagrams if available
        if (data.diagrams) {
            displayDiagrams(data.diagrams);
        }
        
    } catch (error) {
        showError('Network error: ' + error.message);
    } finally {
        hideLoading();
    }
}

function switchTab(tab) {
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
    
    if (tab === 'paste') {
        document.querySelector('.tab-btn').classList.add('active');
        document.getElementById('paste-tab').classList.add('active');
        // Reset filename when switching to paste tab (user might paste new code)
        currentFilename = null;
    } else {
        document.querySelectorAll('.tab-btn')[1].classList.add('active');
        document.getElementById('upload-tab').classList.add('active');
    }
}

// File upload handling
const uploadArea = document.getElementById('upload-area');
const fileInput = document.getElementById('file-input');

if (uploadArea && fileInput) {
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
}

function handleFile(file) {
    // Store filename for language detection
    currentFilename = file.name;
    
    // Check if file extension is supported
    const extension = file.name.toLowerCase().substring(file.name.lastIndexOf('.'));
    const supportedExtensions = [
        '.py', '.pyw', '.pyi',  // Python
        '.js', '.jsx', '.mjs',  // JavaScript
        '.java',                 // Java
        '.c', '.cpp', '.cc', '.cxx', '.h', '.hpp', '.hxx',  // C/C++
        '.php', '.phtml',        // PHP
        '.sql'                   // SQL
    ];
    
    if (!supportedExtensions.includes(extension)) {
        showError(`File extension "${extension}" is not supported. Supported extensions: .py, .js, .jsx, .java, .c, .cpp, .php, .sql`);
        return;
    }
    
    // Prioritize file content: load into text area and switch to paste tab
    const reader = new FileReader();
    reader.onload = (e) => {
        // Set file content in text area (prioritize file content)
        const textarea = document.getElementById('code-input');
        textarea.value = e.target.result;
        currentCode = e.target.result;
        
        // Switch to paste tab to show the loaded content
        switchTab('paste');
        
        // Focus on textarea to show user the content is loaded
        textarea.focus();
        
        // Scroll textarea to top
        textarea.scrollTop = 0;
    };
    reader.onerror = () => {
        showError('Error reading file. Please try again.');
    };
    reader.readAsText(file);
}

async function parseCode() {
    const code = document.getElementById('code-input').value.trim();
    
    if (!code) {
        showError('Please enter or upload some code');
        return;
    }
    
    currentCode = code;
    hideError();
    showLoading();
    
    // Prepare request body with filename for language detection
    const requestBody = { code: code };
    if (currentFilename) {
        requestBody.filename = currentFilename;
    }
    
    try {
        const response = await fetch('/api/parse', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestBody)
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            showError(data.error || 'An error occurred');
            return;
        }
        
        currentData = data;
        
        // Log detected language if available
        if (data.language) {
            console.log(`Detected language: ${data.language}`);
        }
        
        // Show info messages (e.g., JavaScript tree-sitter info)
        if (data.info_messages && data.info_messages.length > 0) {
            data.info_messages.forEach(msg => {
                if (msg.type === 'info') {
                    showInfo(msg.message);
                }
            });
        }
        
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

async function generateDocumentation() {
    // Check if we have project data or single file code
    const isProject = currentData && (currentData.file_details || currentData.project_path || currentData.github_repo_url);
    const isSingleFile = currentCode && currentCode.trim().length > 0;
    
    if (!isProject && !isSingleFile) {
        showError('Please analyze code or parse a project first');
        return;
    }
    
    hideError();
    
    // Show loading state
    const docBtn = document.getElementById('doc-btn');
    const originalText = docBtn.querySelector('span').textContent;
    docBtn.querySelector('span').textContent = 'Generating...';
    docBtn.disabled = true;
    
    try {
        let endpoint, requestBody;
        
        if (isProject) {
            // Generate documentation for project
            endpoint = '/api/generate-project-docs';
            requestBody = {
                project_data: currentData
            };
        } else {
            // Generate documentation for single file
            endpoint = '/api/generate-docs';
            requestBody = {
                code: currentCode
            };
        }
        
        const response = await fetch(endpoint, {
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

function switchDocTab(tab, event) {
    // Hide all tabs
    document.querySelectorAll('.doc-content').forEach(content => {
        content.classList.remove('active');
    });
    document.querySelectorAll('.doc-tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Show selected tab
    document.getElementById(`${tab}-view`).classList.add('active');
    if (event && event.target) {
        event.target.classList.add('active');
    } else {
        // Fallback: find the button by tab name
        document.querySelectorAll('.doc-tab-btn').forEach(btn => {
            if (btn.textContent.trim().toLowerCase().includes(tab.toLowerCase())) {
                btn.classList.add('active');
            }
        });
    }
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

function copyDoc(type, event) {
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
        const btn = (event && event.target) ? event.target.closest('.action-btn') : null;
        if (btn) {
            const originalText = btn.textContent;
            btn.textContent = 'Copied!';
            setTimeout(() => {
                btn.textContent = originalText;
            }, 2000);
        }
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
                <button class="action-btn" onclick="copyToClipboard(event)">
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

function displayProjectSummary(data) {
    const summaryView = document.getElementById('summary-view');
    const summary = data.summary || {};
    const fileDetails = data.file_details || [];
    
    // Store file details globally for filtering
    currentProjectFileDetails = fileDetails;
    
    // Display GitHub repository info card if this is a GitHub repo
    let githubInfoCard = '';
    if (data.github_repo_url) {
        const repoUrl = data.github_repo_url;
        const clonePath = data.cloned_path || 'N/A';
        const totalFiles = summary.total_files || 0;
        const detectedLanguages = data.detected_languages || [];
        const languagesDisplay = detectedLanguages.length > 0 
            ? detectedLanguages.join(', ') 
            : 'None detected';
        
        githubInfoCard = `
            <div style="margin-bottom: 40px;">
                <div style="
                    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
                    border: 2px solid rgba(59, 130, 246, 0.3);
                    border-radius: 16px;
                    padding: 30px;
                    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
                    position: relative;
                    overflow: hidden;
                ">
                    <div style="position: absolute; top: -50%; right: -50%; width: 200%; height: 200%; background: radial-gradient(circle, rgba(59, 130, 246, 0.1) 0%, transparent 70%); opacity: 0.5;"></div>
                    <div style="position: relative; z-index: 1;">
                        <h3 style="color: #60a5fa; margin-bottom: 25px; font-size: 1.4rem; font-weight: 700; display: flex; align-items: center; gap: 10px;">
                            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"></path>
                            </svg>
                            GitHub Repository Information
                        </h3>
                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px;">
                            <div style="padding: 15px; background: rgba(59, 130, 246, 0.1); border-radius: 8px; border-left: 3px solid #3b82f6;">
                                <div style="color: #94a3b8; font-size: 0.85rem; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;">Repository URL</div>
                                <div style="color: #e2e8f0; font-size: 0.95rem; font-family: 'Fira Code', 'Courier New', monospace; word-break: break-all;">
                                    <a href="${repoUrl}" target="_blank" rel="noopener noreferrer" style="color: #60a5fa; text-decoration: none; transition: color 0.2s;" onmouseover="this.style.color='#3b82f6'" onmouseout="this.style.color='#60a5fa'">
                                        ${repoUrl}
                                    </a>
                                </div>
                            </div>
                            <div style="padding: 15px; background: rgba(59, 130, 246, 0.1); border-radius: 8px; border-left: 3px solid #3b82f6;">
                                <div style="color: #94a3b8; font-size: 0.85rem; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;">Local Clone Path</div>
                                <div style="color: #e2e8f0; font-size: 0.95rem; font-family: 'Fira Code', 'Courier New', monospace; word-break: break-all;">
                                    ${clonePath}
                                </div>
                            </div>
                            <div style="padding: 15px; background: rgba(59, 130, 246, 0.1); border-radius: 8px; border-left: 3px solid #3b82f6;">
                                <div style="color: #94a3b8; font-size: 0.85rem; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;">Total Files Parsed</div>
                                <div style="color: #e2e8f0; font-size: 1.5rem; font-weight: 700;">
                                    ${totalFiles.toLocaleString()}
                                </div>
                            </div>
                            <div style="padding: 15px; background: rgba(59, 130, 246, 0.1); border-radius: 8px; border-left: 3px solid #3b82f6;">
                                <div style="color: #94a3b8; font-size: 0.85rem; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;">Languages Detected</div>
                                <div style="color: #e2e8f0; font-size: 0.95rem;">
                                    ${languagesDisplay}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
    
    // Display project summary statistics as metric cards (like Streamlit st.metric)
    let html = `
        ${githubInfoCard}
        <div style="margin-bottom: 40px;">
            <h3 style="color: #60a5fa; margin-bottom: 25px; font-size: 1.3rem; font-weight: 700;">📊 Project Metrics</h3>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 20px; margin-bottom: 30px;">
                <div class="stat-card metric-card">
                    <h3>Total Files</h3>
                    <div class="value">${summary.total_files || 0}</div>
                    <div style="margin-top: 8px; font-size: 0.85rem; color: #94a3b8;">Files parsed</div>
                </div>
                <div class="stat-card metric-card">
                    <h3>Total Lines</h3>
                    <div class="value">${(summary.total_lines || 0).toLocaleString()}</div>
                    <div style="margin-top: 8px; font-size: 0.85rem; color: #94a3b8;">Lines of code</div>
                </div>
                <div class="stat-card metric-card">
                    <h3>Total Functions</h3>
                    <div class="value">${summary.total_functions || 0}</div>
                    <div style="margin-top: 8px; font-size: 0.85rem; color: #94a3b8;">Functions found</div>
                </div>
                <div class="stat-card metric-card">
                    <h3>Total Classes</h3>
                    <div class="value">${summary.total_classes || 0}</div>
                    <div style="margin-top: 8px; font-size: 0.85rem; color: #94a3b8;">Classes found</div>
                </div>
                <div class="stat-card metric-card">
                    <h3>Total Tables</h3>
                    <div class="value">${summary.total_tables || 0}</div>
                    <div style="margin-top: 8px; font-size: 0.85rem; color: #94a3b8;">SQL tables</div>
                </div>
                <div class="stat-card metric-card">
                    <h3>Total Variables</h3>
                    <div class="value">${summary.total_variables || 0}</div>
                    <div style="margin-top: 8px; font-size: 0.85rem; color: #94a3b8;">All variables</div>
                </div>
            </div>
        </div>
        
        <div style="margin-top: 40px; margin-bottom: 30px;">
            <h3 style="color: #60a5fa; margin-bottom: 20px; font-size: 1.3rem;">📁 Files</h3>
            <div style="margin-bottom: 25px;">
                <label style="display: block; margin-bottom: 10px; color: #cbd5e1; font-weight: 600; font-size: 0.95rem;">Select File to View:</label>
                <select id="file-selectbox" onchange="filterFilesBySelection()" style="
                    width: 100%;
                    padding: 12px 16px;
                    border: 2px solid #334155;
                    border-radius: 8px;
                    background: #0f172a;
                    color: #e2e8f0;
                    font-family: 'Fira Code', 'Courier New', monospace;
                    font-size: 0.95rem;
                    cursor: pointer;
                    transition: all 0.3s;
                    appearance: none;
                    background-image: url('data:image/svg+xml;utf8,<svg xmlns=\\'http://www.w3.org/2000/svg\\' width=\\'12\\' height=\\'12\\' viewBox=\\'0 0 12 12\\'><path fill=\\'%2360a5fa\\' d=\\'M6 9L1 4h10z\\'/></svg>');
                    background-repeat: no-repeat;
                    background-position: right 12px center;
                    padding-right: 40px;
                " onfocus="this.style.borderColor='#3b82f6'; this.style.boxShadow='0 0 0 4px rgba(59, 130, 246, 0.2)'" onblur="this.style.borderColor='#334155'; this.style.boxShadow='none'">
                    <option value="all">All Files</option>
                    ${fileDetails.map((fileDetail, index) => {
                        const filePath = fileDetail.path || fileDetail.absolute_path || 'Unknown';
                        return `<option value="${index}">${filePath}</option>`;
                    }).join('')}
                </select>
            </div>
        </div>
        
        <div id="files-container">
    `;
    
    // Render all files initially
    html += renderFileDetails(fileDetails);
    html += `</div>`;
    summaryView.innerHTML = html;
}

function renderFileDetails(fileDetails, selectedIndex = null) {
    if (!fileDetails || fileDetails.length === 0) {
        return `<p style="color: #94a3b8; padding: 20px; text-align: center;">No files found in project.</p>`;
    }
    
    let html = '';
    
    // Filter files if a specific index is selected
    const filesToRender = selectedIndex !== null && selectedIndex !== 'all' 
        ? [fileDetails[parseInt(selectedIndex)]] 
        : fileDetails;
    
    filesToRender.forEach((fileDetail, index) => {
        // Use original index for IDs to maintain consistency
        const originalIndex = selectedIndex !== null && selectedIndex !== 'all' 
            ? parseInt(selectedIndex) 
            : index;
        const fileId = `file-expander-${originalIndex}`;
        const filePath = fileDetail.path || fileDetail.absolute_path || 'Unknown';
        const fileLang = fileDetail.language || 'unknown';
        const functions = fileDetail.functions || [];
        const classes = fileDetail.classes || [];
        const tables = fileDetail.tables || [];
        const relationships = fileDetail.relationships || [];
        const globalVars = fileDetail.global_variables || [];
        const localVars = fileDetail.local_variables || [];
        const execVars = fileDetail.execution_scope_variables || [];
        const imports = fileDetail.imports || [];
        const hasError = fileDetail.error;
        
        // Get language badge color
        const langColors = {
            'python': '#3776ab',
            'javascript': '#f7df1e',
            'jsx': '#61dafb',
            'sql': '#336791',
            'java': '#ed8b00',
            'cpp': '#00599c',
            'c': '#a8b9cc',
            'php': '#777bb4'
        };
        const langColor = langColors[fileLang] || '#666';
        
        html += `
            <div class="file-expander" data-file-index="${originalIndex}" style="margin-bottom: 15px; border: 1px solid #334155; border-radius: 8px; overflow: hidden; background: #1e293b;">
                <div class="file-expander-header" onclick="toggleFileExpander('${fileId}')" style="padding: 15px 20px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); transition: background 0.3s;">
                    <div style="display: flex; align-items: center; gap: 15px; flex: 1;">
                        <span class="file-expander-icon" id="${fileId}-icon" style="transition: transform 0.3s;">▶</span>
                        <div style="flex: 1;">
                            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 5px;">
                                <span style="font-weight: 600; color: #e2e8f0; font-family: 'Fira Code', monospace; font-size: 0.95rem;">${filePath}</span>
                                <span style="padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; background: ${langColor}; color: white;">${fileLang.toUpperCase()}</span>
                                ${hasError ? `<span style="padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; background: #ef4444; color: white;">ERROR</span>` : ''}
                            </div>
                            <div style="display: flex; gap: 15px; font-size: 0.85rem; color: #94a3b8;">
                                ${functions.length > 0 ? `<span>${functions.length} function${functions.length !== 1 ? 's' : ''}</span>` : ''}
                                ${classes.length > 0 ? `<span>${classes.length} class${classes.length !== 1 ? 'es' : ''}</span>` : ''}
                                ${tables.length > 0 ? `<span>${tables.length} table${tables.length !== 1 ? 's' : ''}</span>` : ''}
                                ${imports.length > 0 ? `<span>${imports.length} import${imports.length !== 1 ? 's' : ''}</span>` : ''}
                            </div>
                        </div>
                    </div>
                </div>
                <div class="file-expander-content" id="${fileId}-content" style="display: ${selectedIndex !== null && selectedIndex !== 'all' ? 'block' : 'none'}; padding: 20px; background: #0f172a; border-top: 1px solid #334155;">
                    ${hasError ? `
                        <div style="padding: 15px; background: rgba(239, 68, 68, 0.1); border-left: 3px solid #ef4444; border-radius: 4px; margin-bottom: 20px;">
                            <strong style="color: #ef4444;">Error:</strong> <span style="color: #fca5a5;">${fileDetail.error}</span>
                        </div>
                    ` : ''}
                    ${functions.length > 0 ? `
                        <div style="margin-bottom: 20px;">
                            <h4 style="color: #60a5fa; margin-bottom: 10px; font-size: 1rem;">Functions (${functions.length})</h4>
                            <div style="padding-left: 15px;">
                                ${functions.map(func => `
                                    <div style="margin-bottom: 8px; padding: 8px; background: rgba(59, 130, 246, 0.1); border-radius: 4px; border-left: 3px solid #3b82f6;">
                                        <strong style="color: #60a5fa;">${func.name || 'unnamed'}</strong>
                                        <span style="color: #94a3b8; font-size: 0.85rem; margin-left: 10px;">Line ${func.line || 'N/A'}</span>
                                        ${func.params ? `<div style="color: #cbd5e1; font-size: 0.9rem; margin-top: 4px;">Params: ${func.params.map(p => p.name || p).join(', ') || 'None'}</div>` : ''}
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    ` : ''}
                    ${classes.length > 0 ? `
                        <div style="margin-bottom: 20px;">
                            <h4 style="color: #60a5fa; margin-bottom: 10px; font-size: 1rem;">Classes (${classes.length})</h4>
                            <div style="padding-left: 15px;">
                                ${classes.map(cls => `
                                    <div style="margin-bottom: 8px; padding: 8px; background: rgba(59, 130, 246, 0.1); border-radius: 4px; border-left: 3px solid #3b82f6;">
                                        <strong style="color: #60a5fa;">${cls.name || 'unnamed'}</strong>
                                        <span style="color: #94a3b8; font-size: 0.85rem; margin-left: 10px;">Line ${cls.line || 'N/A'}</span>
                                        ${cls.methods && cls.methods.length > 0 ? `<div style="color: #cbd5e1; font-size: 0.9rem; margin-top: 4px;">Methods: ${cls.methods.length}</div>` : ''}
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    ` : ''}
                    ${tables.length > 0 ? `
                        <div style="margin-bottom: 20px;">
                            <h4 style="color: #60a5fa; margin-bottom: 10px; font-size: 1rem;">Tables (${tables.length})</h4>
                            <div style="padding-left: 15px;">
                                ${tables.map(table => `
                                    <div style="margin-bottom: 8px; padding: 8px; background: rgba(59, 130, 246, 0.1); border-radius: 4px; border-left: 3px solid #3b82f6;">
                                        <strong style="color: #60a5fa;">${table.name || 'unnamed'}</strong>
                                        <span style="color: #94a3b8; font-size: 0.85rem; margin-left: 10px;">Line ${table.line || 'N/A'}</span>
                                        ${table.columns ? `<div style="color: #cbd5e1; font-size: 0.9rem; margin-top: 4px;">Columns: ${table.columns.length}</div>` : ''}
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    ` : ''}
                    ${(globalVars.length > 0 || localVars.length > 0 || execVars.length > 0) ? `
                        <div style="margin-bottom: 20px;">
                            <h4 style="color: #60a5fa; margin-bottom: 10px; font-size: 1rem;">Variables</h4>
                            <div style="padding-left: 15px;">
                                ${globalVars.length > 0 ? `<div style="margin-bottom: 8px;"><strong style="color: #94a3b8;">Global:</strong> ${globalVars.map(v => v.name || v.variable || 'unknown').join(', ') || 'None'}</div>` : ''}
                                ${localVars.length > 0 ? `<div style="margin-bottom: 8px;"><strong style="color: #94a3b8;">Local:</strong> ${localVars.map(v => v.name || v.variable || 'unknown').join(', ') || 'None'}</div>` : ''}
                                ${execVars.length > 0 ? `<div style="margin-bottom: 8px;"><strong style="color: #94a3b8;">Execution Scope:</strong> ${execVars.map(v => v.name || v.variable || 'unknown').join(', ') || 'None'}</div>` : ''}
                            </div>
                        </div>
                    ` : ''}
                    ${imports.length > 0 ? `
                        <div style="margin-bottom: 20px;">
                            <h4 style="color: #60a5fa; margin-bottom: 10px; font-size: 1rem;">Imports (${imports.length})</h4>
                            <div style="padding-left: 15px; color: #cbd5e1; font-size: 0.9rem;">
                                ${imports.map(imp => imp.module || imp.name || JSON.stringify(imp)).join(', ')}
                            </div>
                        </div>
                    ` : ''}
                    ${!hasError && functions.length === 0 && classes.length === 0 && tables.length === 0 && globalVars.length === 0 && localVars.length === 0 && execVars.length === 0 && imports.length === 0 ? `
                        <div style="color: #94a3b8; text-align: center; padding: 20px;">
                            No code elements found in this file.
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    });
    
    return html;
}

function filterFilesBySelection() {
    const selectbox = document.getElementById('file-selectbox');
    const selectedValue = selectbox.value;
    const filesContainer = document.getElementById('files-container');
    
    if (!currentProjectFileDetails || !filesContainer) {
        return;
    }
    
    // Re-render files based on selection
    filesContainer.innerHTML = renderFileDetails(currentProjectFileDetails, selectedValue);
    
    // If a specific file is selected, auto-expand it
    if (selectedValue !== 'all' && selectedValue !== null) {
        const fileIndex = parseInt(selectedValue);
        const fileId = `file-expander-${fileIndex}`;
        const content = document.getElementById(`${fileId}-content`);
        const icon = document.getElementById(`${fileId}-icon`);
        
        if (content && icon) {
            content.style.display = 'block';
            icon.textContent = '▼';
        }
    }
}

function toggleFileExpander(fileId) {
    const content = document.getElementById(`${fileId}-content`);
    const icon = document.getElementById(`${fileId}-icon`);
    
    if (content.style.display === 'none') {
        content.style.display = 'block';
        icon.textContent = '▼';
        icon.style.transform = 'rotate(0deg)';
    } else {
        content.style.display = 'none';
        icon.textContent = '▶';
        icon.style.transform = 'rotate(0deg)';
    }
}

function displaySummary(data) {
    const summaryView = document.getElementById('summary-view');
    const summary = data.summary;
    const language = (data.language || 'python').toLowerCase();
    
    // Reset variable section counter
    varSectionCounter = 0;
    
    // Check if this is a project result (has file_details or project_path)
    if (data.file_details || data.project_path) {
        displayProjectSummary(data);
        return;
    }
    
    // Check if SQL - show SQL-specific stats
    if (language === 'sql') {
        // Count primary keys across all tables
        const totalPrimaryKeys = data.tables ? data.tables.reduce((sum, t) => {
            return sum + (t.columns ? t.columns.filter(c => c.is_primary_key).length : 0);
        }, 0) : 0;
        
        summaryView.innerHTML = `
            <div class="stat-card">
                <h3>Total Tables</h3>
                <div class="value">${summary.total_tables || 0}</div>
            </div>
            <div class="stat-card">
                <h3>Primary Keys</h3>
                <div class="value">${totalPrimaryKeys}</div>
                <div style="margin-top: 10px; font-size: 0.85rem; color: #666;">
                    🔑 Primary key columns
                </div>
            </div>
            <div class="stat-card">
                <h3>Relationships</h3>
                <div class="value">${summary.total_relationships || 0}</div>
                <div style="margin-top: 10px; font-size: 0.85rem; color: #666;">
                    Foreign key relationships
                </div>
            </div>
            <div class="stat-card">
                <h3>Total Columns</h3>
                <div class="value">${data.tables ? data.tables.reduce((sum, t) => sum + (t.columns ? t.columns.length : 0), 0) : 0}</div>
            </div>
        `;
        
        // Add tables section
        if (data.tables && data.tables.length > 0) {
            summaryView.innerHTML += createDetailSection('Tables', data.tables, (table) => {
                const columns = table.columns || [];
                const pkCols = columns.filter(c => c.is_primary_key).map(c => c.name);
                const fkCols = columns.filter(c => c.is_foreign_key).map(c => c.name);
                
                return `
                    <div class="detail-item">
                        <div class="name">${table.name}</div>
                        <div class="meta">
                            <span>Line: ${table.line || 'N/A'}</span>
                            <span>Columns: ${columns.length}</span>
                            ${pkCols.length > 0 ? `<span style="color: #FF9800; font-weight: 600;">🔑 Primary Key: ${pkCols.join(', ')}</span>` : '<span style="color: #999;">No primary key</span>'}
                            ${fkCols.length > 0 ? `<span>🔗 FK: ${fkCols.length} foreign key(s)</span>` : ''}
                        </div>
                        ${columns.length > 0 ? `
                            <div style="margin-top: 10px; padding-left: 20px; border-left: 2px solid #ddd;">
                                <strong>Columns:</strong>
                                <div style="margin-top: 5px; font-size: 0.9em;">
                                    ${columns.map(col => {
                                        const constraints = [];
                                        let colStyle = 'margin: 3px 0;';
                                        let nameStyle = '';
                                        
                                        if (col.is_primary_key) {
                                            constraints.push('PK');
                                            colStyle += ' background: #fff3e0; padding: 4px 8px; border-radius: 4px; border-left: 3px solid #FF9800;';
                                            nameStyle = 'font-weight: 600; color: #FF9800;';
                                        }
                                        if (col.is_foreign_key) constraints.push('FK');
                                        if (col.is_unique) constraints.push('UNIQUE');
                                        if (col.is_not_null) constraints.push('NOT NULL');
                                        
                                        const constraintStr = constraints.length > 0 ? ` <span style="color: #666;">[${constraints.join(', ')}]</span>` : '';
                                        return `<div style="${colStyle}">• <span style="${nameStyle}">${col.name}</span> <span style="color: #2196F3;">${col.type || 'unknown'}</span>${constraintStr}</div>`;
                                    }).join('')}
                                </div>
                            </div>
                        ` : ''}
                    </div>
                `;
            });
        }
        
        // Add relationships section
        if (data.relationships && data.relationships.length > 0) {
            summaryView.innerHTML += createDetailSection('Foreign Key Relationships', data.relationships, (rel) => {
                return `
                    <div class="detail-item">
                        <div class="name">${rel.from_table}.${rel.from_column} → ${rel.to_table}.${rel.to_column}</div>
                        <div class="meta">
                            <span>Type: ${rel.type || 'foreign_key'}</span>
                        </div>
                    </div>
                `;
            });
        }
        
        return; // Exit early for SQL
    }
    
    // Python/JavaScript display (original code)
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
            <h3>Variables</h3>
            <div class="value">${(summary.global_variables || 0) + (summary.local_variables || 0) + (summary.execution_scope_variables || 0)}</div>
            <div style="margin-top: 10px; font-size: 0.85rem; color: #666;">
                ${summary.global_variables || 0} global, ${summary.local_variables || 0} local, ${summary.execution_scope_variables || 0} execution-scope
            </div>
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
                <div class="detail-item clickable-item" onclick="scrollToLine(${f.line}, 'function')" data-line="${f.line}" style="cursor: pointer;">
                    <div class="name">${f.name} <span class="line-link-hint">(click to jump)</span></div>
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
            // Format class name with base classes: "ClassName(BaseClass)"
            const classNameDisplay = c.bases.length > 0 
                ? `${c.name}(${c.bases.join(', ')})` 
                : c.name;
            
            return `
                <div class="detail-item clickable-item" onclick="scrollToLine(${c.line}, 'class')" data-line="${c.line}" style="cursor: pointer;">
                    <div class="name">${classNameDisplay} <span class="line-link-hint">(click to jump)</span></div>
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
    
    // Create collapsible variable sections grouped by scope
    summaryView.innerHTML += '<div class="variables-container">';
    
    // Global Variables Section
    if (data.global_variables && data.global_variables.length > 0) {
        summaryView.innerHTML += createCollapsibleVariableSection(
            'Global Variables',
            data.global_variables,
            (v) => {
                return `
                    <div class="detail-item clickable-item" onclick="scrollToLine(${v.line}, 'variable')" data-line="${v.line}" style="cursor: pointer;">
                        <div class="name">${v.name} <span class="line-link-hint">(click to jump)</span></div>
                        <div class="meta">
                            <span>Line: ${v.line}</span>
                            ${v.type && v.type !== 'unknown' ? `<span>Type: ${v.type}</span>` : ''}
                        </div>
                    </div>
                `;
            },
            'global'
        );
    }
    
    // Execution-Scope Variables Section
    if (data.execution_scope_variables && data.execution_scope_variables.length > 0) {
        summaryView.innerHTML += createCollapsibleVariableSection(
            'Execution-Scope Variables',
            data.execution_scope_variables,
            (v) => {
                return `
                    <div class="detail-item clickable-item" onclick="scrollToLine(${v.line}, 'variable')" data-line="${v.line}" style="cursor: pointer;">
                        <div class="name">${v.name} <span class="line-link-hint">(click to jump)</span></div>
                        <div class="meta">
                            <span>Line: ${v.line}</span>
                            <span>In: if __name__ == "__main__"</span>
                            ${v.type && v.type !== 'unknown' ? `<span>Type: ${v.type}</span>` : ''}
                        </div>
                    </div>
                `;
            },
            'execution-scope'
        );
    }
    
    // Collect all class variables
    const allClassVars = [];
    if (data.classes && data.classes.length > 0) {
        data.classes.forEach(cls => {
            if (cls.class_variables && cls.class_variables.length > 0) {
                cls.class_variables.forEach(v => {
                    allClassVars.push({
                        ...v,
                        className: cls.name
                    });
                });
            }
        });
    }
    
    // Class Variables Section
    if (allClassVars.length > 0) {
        summaryView.innerHTML += createCollapsibleVariableSection(
            'Class Variables',
            allClassVars,
            (v) => {
                return `
                    <div class="detail-item clickable-item" onclick="scrollToLine(${v.line}, 'variable')" data-line="${v.line}" style="cursor: pointer;">
                        <div class="name">${v.name} <span class="line-link-hint">(click to jump)</span></div>
                        <div class="meta">
                            <span>Line: ${v.line}</span>
                            <span>In: ${v.className}</span>
                            ${v.type && v.type !== 'unknown' ? `<span>Type: ${v.type}</span>` : ''}
                        </div>
                    </div>
                `;
            },
            'class'
        );
    }
    
    // Collect all instance variables
    const allInstanceVars = [];
    if (data.classes && data.classes.length > 0) {
        data.classes.forEach(cls => {
            if (cls.instance_variables && cls.instance_variables.length > 0) {
                cls.instance_variables.forEach(v => {
                    allInstanceVars.push({
                        ...v,
                        className: cls.name
                    });
                });
            }
        });
    }
    
    // Instance Variables Section
    if (allInstanceVars.length > 0) {
        summaryView.innerHTML += createCollapsibleVariableSection(
            'Instance Variables',
            allInstanceVars,
            (v) => {
                return `
                    <div class="detail-item clickable-item" onclick="scrollToLine(${v.line}, 'variable')" data-line="${v.line}" style="cursor: pointer;">
                        <div class="name">${v.name} <span class="line-link-hint">(click to jump)</span></div>
                        <div class="meta">
                            <span>Line: ${v.line}</span>
                            <span>In: ${v.className}</span>
                            ${v.type && v.type !== 'unknown' ? `<span>Type: ${v.type}</span>` : ''}
                        </div>
                    </div>
                `;
            },
            'instance'
        );
    }
    
    // Local Variables Section (grouped by function)
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
        
        // Create a flat list with function context
        const allLocalVars = [];
        Object.keys(varsByFunction).forEach(funcName => {
            varsByFunction[funcName].forEach(v => {
                allLocalVars.push({
                    ...v,
                    functionName: funcName
                });
            });
        });
        
        summaryView.innerHTML += createCollapsibleVariableSection(
            'Local Variables',
            allLocalVars,
            (v) => {
                return `
                    <div class="detail-item clickable-item" onclick="scrollToLine(${v.line}, 'variable')" data-line="${v.line}" style="cursor: pointer;">
                        <div class="name">${v.name} <span class="line-link-hint">(click to jump)</span></div>
                        <div class="meta">
                            <span>Line: ${v.line}</span>
                            <span>In: ${v.functionName}</span>
                            ${v.type && v.type !== 'unknown' ? `<span>Type: ${v.type}</span>` : ''}
                        </div>
                    </div>
                `;
            },
            'local'
        );
    }
    
    summaryView.innerHTML += '</div>';
    
    // Code Insights Section (Warnings)
    if (data.warnings && data.warnings.length > 0) {
        summaryView.innerHTML += createDetailSection('Code Insights', data.warnings, (w) => {
            const severityColors = {
                'warning': '#FF9800',
                'error': '#F44336',
                'info': '#2196F3'
            };
            const severityIcons = {
                'warning': '⚠️',
                'error': '❌',
                'info': 'ℹ️'
            };
            const color = severityColors[w.severity] || '#666';
            const icon = severityIcons[w.severity] || 'ℹ️';
            
            let details = '';
            if (w.type === 'shadowed_variable' || w.type === 'global_override') {
                details = `<span>Global defined at line ${w.global_line}</span>`;
            } else if (w.type === 'duplicate_function' || w.type === 'duplicate_class') {
                details = `<span>Previous definition at line ${w.previous_line}</span>`;
            } else if (w.type === 'duplicate_variable') {
                details = `<span>Previous definition at line ${w.previous_line}</span>`;
            }
            
            return `
                <div class="detail-item warning-item" onclick="${w.line ? `scrollToLine(${w.line}, 'variable')` : ''}" style="cursor: ${w.line ? 'pointer' : 'default'};">
                    <div class="name">
                        <span style="color: ${color}; margin-right: 8px;">${icon}</span>
                        ${w.message}
                    </div>
                    <div class="meta">
                        ${w.line ? `<span>Line: ${w.line}</span>` : ''}
                        ${w.function ? `<span>In: ${w.function}</span>` : ''}
                        ${details}
                        <span style="color: ${color}; font-weight: 600;">${w.severity.toUpperCase()}</span>
                    </div>
                </div>
            `;
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

function createCollapsibleVariableSection(title, items, itemRenderer, scopeType) {
    if (items.length === 0) return '';
    
    varSectionCounter++;
    const sectionId = `var-section-${scopeType}-${varSectionCounter}`;
    const contentId = `var-content-${scopeType}-${varSectionCounter}`;
    
    // Scope-specific colors
    const scopeColors = {
        'global': '#4CAF50',
        'execution-scope': '#FF9800',
        'class': '#9C27B0',
        'instance': '#E91E63',
        'local': '#2196F3'
    };
    
    const color = scopeColors[scopeType] || '#666';
    
    return `
        <div class="collapsible-var-section">
            <button class="collapsible-var-header" onclick="toggleVariableSection('${contentId}', '${sectionId}')" id="${sectionId}">
                <span class="var-section-title" style="color: ${color};">
                    ${title}
                </span>
                <span class="var-section-count">(${items.length})</span>
                <span class="var-section-toggle">▼</span>
            </button>
            <div class="collapsible-var-content" id="${contentId}" style="display: block;">
                ${items.map(itemRenderer).join('')}
            </div>
        </div>
    `;
}

function toggleVariableSection(contentId, headerId) {
    const content = document.getElementById(contentId);
    const header = document.getElementById(headerId);
    const toggle = header.querySelector('.var-section-toggle');
    
    if (content.style.display === 'none') {
        content.style.display = 'block';
        toggle.textContent = '▼';
    } else {
        content.style.display = 'none';
        toggle.textContent = '▶';
    }
}

function scrollToLine(lineNumber, type) {
    const textarea = document.getElementById('code-input');
    if (!textarea || !currentCode) {
        return;
    }
    
    // Switch to paste tab if not already there
    switchTab('paste');
    
    // Calculate character positions for the line
    const lines = currentCode.split('\n');
    let startChar = 0;
    
    // Sum characters up to the target line (lineNumber is 1-indexed)
    for (let i = 0; i < lineNumber - 1 && i < lines.length; i++) {
        startChar += lines[i].length + 1; // +1 for newline
    }
    
    // Calculate end of line
    const endChar = startChar + (lines[lineNumber - 1] ? lines[lineNumber - 1].length : 0);
    
    // Set selection to highlight the entire line
    textarea.focus();
    textarea.setSelectionRange(startChar, endChar);
    
    // Scroll to the line - center it in view
    const lineHeight = parseFloat(getComputedStyle(textarea).lineHeight) || 25.2;
    const scrollTop = (lineNumber - 1) * lineHeight - textarea.clientHeight / 2;
    textarea.scrollTop = Math.max(0, scrollTop);
    
    // Add visual highlight effect
    highlightLine(textarea, lineNumber, type);
    
    // Scroll the page to show the textarea if needed
    setTimeout(() => {
        textarea.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 100);
}

function highlightLine(textarea, lineNumber, type) {
    // Remove any existing highlight
    const existingHighlight = document.getElementById('line-highlight');
    if (existingHighlight) {
        existingHighlight.remove();
    }
    
    // Add temporary class to textarea for visual feedback
    textarea.classList.add('line-highlight-active');
    
    // Remove the class after animation
    setTimeout(() => {
        textarea.classList.remove('line-highlight-active');
    }, 1500);
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

function copyToClipboard(event) {
    if (!currentData) return;
    
    const jsonString = JSON.stringify(currentData, null, 2);
    navigator.clipboard.writeText(jsonString).then(() => {
        const btn = (event && event.target) ? event.target.closest('.action-btn') : null;
        if (btn) {
            const span = btn.querySelector('span');
            if (span) {
                const originalText = span.textContent;
                span.textContent = 'Copied!';
                setTimeout(() => {
                    span.textContent = originalText;
                }, 2000);
            }
        }
    });
}

function showError(message) {
    const errorDiv = document.getElementById('error-message');
    errorDiv.textContent = message;
    errorDiv.className = 'error-message';
    errorDiv.style.display = 'block';
}

function showInfo(message) {
    const errorDiv = document.getElementById('error-message');
    errorDiv.textContent = message;
    errorDiv.className = 'info-message';
    errorDiv.style.display = 'block';
    // Auto-hide info messages after 5 seconds
    setTimeout(() => {
        if (errorDiv.className === 'info-message') {
            hideError();
        }
    }, 5000);
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
        
        // Clean the diagram code - remove markdown code fences
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
                    flowchart: { useMaxWidth: true, htmlLabels: true },
                    sequence: { diagramMarginX: 50, diagramMarginY: 10 },
                    graph: { useMaxWidth: true, htmlLabels: true }
                });
                window.mermaidInitialized = true;
            } catch (err) {
                console.error('Error initializing Mermaid:', err);
            }
        }
        
        // Clear the element first
        element.innerHTML = '';
        
        // Ensure the element has the mermaid class
        element.classList.add('mermaid');
        
        // Set the diagram code as text content (Mermaid will parse this)
        element.textContent = cleanCode;
        
        // Render the diagram using mermaid.render for more reliable rendering
        setTimeout(() => {
            try {
                // Use mermaid.render which is more reliable for v10+
                if (typeof mermaid.render === 'function') {
                    const uniqueId = `mermaid-${elementId}-${Date.now()}`;
                    mermaid.render(uniqueId, cleanCode).then(({ svg, bindFunctions }) => {
                        element.innerHTML = svg;
                        if (bindFunctions) {
                            bindFunctions(element);
                        }
                        console.log(`Successfully rendered ${elementId} using mermaid.render`);
                    }).catch(err => {
                        console.error(`Error rendering ${elementId} with mermaid.render:`, err);
                        // Fallback to mermaid.run
                        if (typeof mermaid.run === 'function') {
                            element.textContent = cleanCode;
                            mermaid.run({ 
                                nodes: [element],
                                suppressErrors: false
                            }).then(() => {
                                console.log(`Successfully rendered ${elementId} using mermaid.run`);
                            }).catch(runErr => {
                                console.error('mermaid.run also failed:', runErr);
                                element.innerHTML = `<div style="color: #c33; padding: 20px; background: #fff3f3; border: 1px solid #ffcccc; border-radius: 4px;">
                                    <p><strong>⚠️ Error rendering diagram:</strong></p>
                                    <p style="font-size: 0.9em;">${err.message || runErr.message || 'Unknown error'}</p>
                                    <details style="margin-top: 10px;">
                                        <summary style="cursor: pointer; color: #666;">Show diagram code</summary>
                                        <pre style="font-size: 0.75em; overflow: auto; max-height: 300px; background: #f5f5f5; padding: 10px; margin-top: 10px; border: 1px solid #ddd; border-radius: 4px; white-space: pre-wrap;">${cleanCode}</pre>
                                    </details>
                                </div>`;
                            });
                        } else {
                            element.innerHTML = `<div style="color: #c33; padding: 20px; background: #fff3f3; border: 1px solid #ffcccc; border-radius: 4px;">
                                <p><strong>⚠️ Error rendering diagram:</strong></p>
                                <p style="font-size: 0.9em;">${err.message || 'Unknown error'}</p>
                                <details style="margin-top: 10px;">
                                    <summary style="cursor: pointer; color: #666;">Show diagram code</summary>
                                    <pre style="font-size: 0.75em; overflow: auto; max-height: 300px; background: #f5f5f5; padding: 10px; margin-top: 10px; border: 1px solid #ddd; border-radius: 4px; white-space: pre-wrap;">${cleanCode}</pre>
                                </details>
                            </div>`;
                        }
                    });
                } else if (typeof mermaid.run === 'function') {
                    // Fallback to mermaid.run
                    mermaid.run({ 
                        nodes: [element],
                        suppressErrors: false
                    }).then(() => {
                        console.log(`Successfully rendered ${elementId} using mermaid.run`);
                    }).catch(err => {
                        console.error(`Error rendering ${elementId}:`, err);
                        element.innerHTML = `<div style="color: #c33; padding: 20px; background: #fff3f3; border: 1px solid #ffcccc; border-radius: 4px;">
                            <p><strong>⚠️ Error rendering diagram:</strong></p>
                            <p style="font-size: 0.9em;">${err.message || 'Unknown error'}</p>
                            <details style="margin-top: 10px;">
                                <summary style="cursor: pointer; color: #666;">Show diagram code</summary>
                                <pre style="font-size: 0.75em; overflow: auto; max-height: 300px; background: #f5f5f5; padding: 10px; margin-top: 10px; border: 1px solid #ddd; border-radius: 4px; white-space: pre-wrap;">${cleanCode}</pre>
                            </details>
                        </div>`;
                    });
                } else if (typeof mermaid.init === 'function') {
                    // Fallback for older Mermaid versions
                    mermaid.init(undefined, element);
                } else {
                    element.innerHTML = '<p style="color: #c33;">Mermaid.js version not supported. Please update to v10+.</p>';
                }
            } catch (err) {
                console.error(`Error rendering ${elementId}:`, err);
                element.innerHTML = `<p style="color: #c33;">Error rendering diagram: ${err.message}</p>`;
            }
        }, 100);
    };
    
    // Render all diagrams
    // Use code_architecture if available, otherwise fall back to architecture
    const architectureDiagram = diagrams.code_architecture || diagrams.architecture;
    renderDiagram('architecture-mermaid', architectureDiagram);
    renderDiagram('sequence-mermaid', diagrams.sequence);
    renderDiagram('dependencies-mermaid', diagrams.dependencies);
    renderDiagram('flowchart-mermaid', diagrams.flowchart);
    renderDiagram('structure-mermaid', diagrams.structure);
}

function switchDiagramTab(tab, event) {
    // Hide all tabs
    document.querySelectorAll('.diagram-content').forEach(content => {
        content.classList.remove('active');
    });
    document.querySelectorAll('.diagram-tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Show selected tab
    document.getElementById(`${tab}-diagram`).classList.add('active');
    if (event && event.target) {
        event.target.classList.add('active');
    } else {
        // Fallback: find the button by tab name
        document.querySelectorAll('.diagram-tab-btn').forEach(btn => {
            if (btn.textContent.trim().toLowerCase().includes(tab.toLowerCase())) {
                btn.classList.add('active');
            }
        });
    }
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

async function parseProject() {
    const folderPath = document.getElementById('folder-path-input').value.trim();
    
    if (!folderPath) {
        showError('Please enter a folder path');
        return;
    }
    
    hideError();
    showLoading();
    
    try {
        const response = await fetch('/api/parse-project', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                folder_path: folderPath
            })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            showError(data.error || 'An error occurred while parsing the project');
            return;
        }
        
        currentData = data;
        
        // Log detected language if available
        if (data.language) {
            console.log(`Detected language: ${data.language}`);
        }
        
        // Show info messages
        if (data.info_messages && data.info_messages.length > 0) {
            data.info_messages.forEach(msg => {
                if (msg.type === 'info') {
                    showInfo(msg.message);
                }
            });
        }
        
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

