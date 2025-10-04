// CloudBuccaneer Web UI JavaScript

// Tab switching functionality
document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
        // Remove active class from all tabs and content
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        
        // Add active class to clicked tab and corresponding content
        tab.classList.add('active');
        const tabId = tab.getAttribute('data-tab');
        document.getElementById(tabId).classList.add('active');
    });
});

// Utility function to show results
function showResult(elementId, message, type = 'info') {
    const resultEl = document.getElementById(elementId);
    resultEl.className = `result show ${type}`;
    resultEl.innerHTML = message;
}

// Utility function to set button loading state
function setButtonLoading(button, isLoading) {
    if (isLoading) {
        button.classList.add('loading');
        button.disabled = true;
    } else {
        button.classList.remove('loading');
        button.disabled = false;
    }
}

// Fetch/Download Form
document.getElementById('fetch-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const button = e.target.querySelector('button[type="submit"]');
    setButtonLoading(button, true);
    
    const url = document.getElementById('fetch-url').value.trim();
    const dest = document.getElementById('fetch-dest').value.trim() || null;
    const maxSeconds = document.getElementById('fetch-max-seconds').value || null;
    
    try {
        const response = await fetch('/api/fetch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url,
                dest,
                max_seconds: maxSeconds ? parseInt(maxSeconds) : null
            })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            showResult('fetch-result', `
                <h3>✅ Download Successful!</h3>
                <p><strong>Platform:</strong> ${data.platform}</p>
                <p><strong>Destination:</strong> ${data.destination}</p>
            `, 'success');
        } else {
            showResult('fetch-result', `
                <h3>❌ Download Failed</h3>
                <p>${data.detail || 'An error occurred during download'}</p>
            `, 'error');
        }
    } catch (error) {
        showResult('fetch-result', `
            <h3>❌ Error</h3>
            <p>${error.message}</p>
        `, 'error');
    } finally {
        setButtonLoading(button, false);
    }
});

// Search Form
document.getElementById('search-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const button = e.target.querySelector('button[type="submit"]');
    setButtonLoading(button, true);
    
    const query = document.getElementById('search-query').value.trim();
    const kind = document.getElementById('search-kind').value;
    const maxResults = parseInt(document.getElementById('search-max').value);
    
    try {
        const response = await fetch('/api/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, kind, max_results: maxResults })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            if (data.results.length === 0) {
                showResult('search-results', `
                    <h3>No Results Found</h3>
                    <p>Try a different search query or type.</p>
                `, 'info');
            } else {
                let resultsHTML = `<h3>🔍 Found ${data.results.length} Results</h3><div class="mt-2">`;
                
                data.results.forEach(result => {
                    resultsHTML += `
                        <div class="search-item">
                            <div class="search-item-title">${result.title}</div>
                            <a href="${result.url}" target="_blank" class="search-item-url" style="text-decoration: none;">${result.url}</a>
                            <button class="download-btn" onclick="downloadFromSearch('${result.url}')">Download</button>
                        </div>
                    `;
                });
                
                resultsHTML += '</div>';
                showResult('search-results', resultsHTML, 'success');
            }
        } else {
            showResult('search-results', `
                <h3>❌ Search Failed</h3>
                <p>${data.detail || 'An error occurred during search'}</p>
            `, 'error');
        }
    } catch (error) {
        showResult('search-results', `
            <h3>❌ Error</h3>
            <p>${error.message}</p>
        `, 'error');
    } finally {
        setButtonLoading(button, false);
    }
});

// Download from search results
async function downloadFromSearch(url) {
    document.getElementById('fetch-url').value = url;
    
    // Switch to fetch tab
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.querySelector('[data-tab="fetch"]').classList.add('active');
    document.getElementById('fetch').classList.add('active');
    
    // Scroll to top
    window.scrollTo({ top: 0, behavior: 'smooth' });
    
    showResult('fetch-result', `
        <h3>ℹ️ Ready to Download</h3>
        <p>URL has been filled. Click "Download" to start.</p>
    `, 'info');
}

// Rename Form
document.getElementById('rename-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const button = e.target.querySelector('button[type="submit"]');
    setButtonLoading(button, true);
    
    const folder = document.getElementById('rename-folder').value.trim();
    
    try {
        const response = await fetch('/api/rename', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ folder })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            showResult('rename-result', `
                <h3>✅ Rename Complete</h3>
                <p>${data.message}</p>
                ${data.count > 0 ? `<p><strong>${data.count}</strong> file(s) renamed</p>` : ''}
            `, 'success');
        } else {
            showResult('rename-result', `
                <h3>❌ Rename Failed</h3>
                <p>${data.detail || 'An error occurred during renaming'}</p>
            `, 'error');
        }
    } catch (error) {
        showResult('rename-result', `
            <h3>❌ Error</h3>
            <p>${error.message}</p>
        `, 'error');
    } finally {
        setButtonLoading(button, false);
    }
});

// Clean Form
document.getElementById('clean-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const button = e.target.querySelector('button[type="submit"]');
    setButtonLoading(button, true);
    
    const folder = document.getElementById('clean-folder').value.trim();
    const images = document.getElementById('clean-images').checked;
    const webp = document.getElementById('clean-webp').checked;
    const parts = document.getElementById('clean-parts').checked;
    
    try {
        const response = await fetch('/api/clean', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ folder, images, webp, parts })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            showResult('clean-result', `
                <h3>✅ Clean Complete</h3>
                <p>${data.message}</p>
                ${data.count > 0 ? `<p><strong>${data.count}</strong> file(s) removed</p>` : ''}
            `, 'success');
        } else {
            showResult('clean-result', `
                <h3>❌ Clean Failed</h3>
                <p>${data.detail || 'An error occurred during cleaning'}</p>
            `, 'error');
        }
    } catch (error) {
        showResult('clean-result', `
            <h3>❌ Error</h3>
            <p>${error.message}</p>
        `, 'error');
    } finally {
        setButtonLoading(button, false);
    }
});

// BPM Form
document.getElementById('bpm-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const button = e.target.querySelector('button[type="submit"]');
    setButtonLoading(button, true);
    
    const target = document.getElementById('bpm-target').value.trim();
    const advanced = document.getElementById('bpm-advanced').checked;
    const parallel = document.getElementById('bpm-parallel').checked;
    
    try {
        const response = await fetch('/api/bpm', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ target, advanced, parallel })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            let resultsHTML = `<h3>🎵 BPM Analysis Complete</h3>`;
            resultsHTML += `<p><strong>Total:</strong> ${data.total} file(s) analyzed</p>`;
            resultsHTML += '<div class="bpm-results">';
            
            data.results.forEach(result => {
                resultsHTML += `
                    <div class="bpm-item">
                        <strong>${result.file}</strong>: ${result.bpm !== null ? result.bpm + ' BPM' : 'Unable to detect'}
                    </div>
                `;
            });
            
            resultsHTML += '</div>';
            showResult('bpm-result', resultsHTML, 'success');
        } else {
            showResult('bpm-result', `
                <h3>❌ BPM Detection Failed</h3>
                <p>${data.detail || 'An error occurred during BPM detection'}</p>
            `, 'error');
        }
    } catch (error) {
        showResult('bpm-result', `
            <h3>❌ Error</h3>
            <p>${error.message}</p>
        `, 'error');
    } finally {
        setButtonLoading(button, false);
    }
});

// Load Config Button
document.getElementById('load-config-btn').addEventListener('click', async () => {
    const button = document.getElementById('load-config-btn');
    setButtonLoading(button, true);
    
    try {
        const response = await fetch('/api/config');
        const data = await response.json();
        
        if (response.ok) {
            const configHTML = `
                <div class="config-display">
                    <pre>${JSON.stringify(data, null, 2)}</pre>
                </div>
            `;
            showResult('config-display', configHTML, 'info');
        } else {
            showResult('config-display', `
                <h3>❌ Failed to Load Config</h3>
                <p>${data.detail || 'An error occurred'}</p>
            `, 'error');
        }
    } catch (error) {
        showResult('config-display', `
            <h3>❌ Error</h3>
            <p>${error.message}</p>
        `, 'error');
    } finally {
        setButtonLoading(button, false);
    }
});

// Initialize - show welcome message
window.addEventListener('DOMContentLoaded', () => {
    console.log('CloudBuccaneer Web UI loaded successfully! ☁️🏴‍☠️');
});
