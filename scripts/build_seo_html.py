#!/usr/bin/env python3
"""Convert forge/seo/*.md to web/forge/seo/*.html with proper headers/footers."""
import os, re, sys

WEB_ROOT = '/var/www/devbench/web'
FORGE_SEO_SRC = '/var/www/devbench/forge/seo'
WEB_SEO_DST = os.path.join(WEB_ROOT, 'forge', 'seo')

HEADER_FILE = os.path.join(FORGE_SEO_SRC, '_header.html')
FOOTER_FILE = os.path.join(FORGE_SEO_SRC, '_footer.html')

def markdown_to_html(text):
    """Basic MD-to-HTML conversion for SEO pages (code blocks, headers, links, lists)."""
    lines = text.split('\n')
    html_lines = []
    in_code_block = False
    in_table = False
    code_lang = ''
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Code blocks
        if line.startswith('```'):
            if in_code_block:
                html_lines.append('</code></pre>\n')
                in_code_block = False
            else:
                lang = line[3:].strip()
                html_lines.append(f'<pre><code class="language-{lang}">\n')
                in_code_block = True
            i += 1
            continue
        
        if in_code_block:
            escaped = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            html_lines.append(escaped + '\n')
            i += 1
            continue
        
        # Horizontal rules
        if re.match(r'^-{3,}$', line):
            html_lines.append('<hr />\n')
            i += 1
            continue
        
        # Headers
        h_match = re.match(r'^(#{1,6})\s+(.+)$', line)
        if h_match:
            level = len(h_match.group(1))
            title = h_match.group(2)
            # Extract id for anchors
            anchor_id = title.lower().replace(' ', '-').replace(':', '').replace('/', '-')
            anchor_id = re.sub(r'[^a-z0-9\-]', '', anchor_id)
            html_lines.append(f'<h{level} id="{anchor_id}">{title}</h{level}>\n')
            i += 1
            continue
        
        # Tables
        if '|' in line and line.strip().startswith('|'):
            cells = [c.strip() for c in line.split('|') if c.strip()]
            if re.match(r'^[\|\s\-:]+$', line):  # separator row
                html_lines.append(line + '\n')  # keep for processing
            else:
                html_lines.append(f'<tr>{"".join(f"<td>{c}</td>" for c in cells)}</tr>\n')
            i += 1
            continue
        
        # Links [text](url)
        line = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', line)
        
        # Bold **text**
        line = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', line)
        
        # Inline code
        line = re.sub(r'`([^`]+)`', r'<code>\1</code>', line)
        
        # Empty line
        if not line.strip():
            html_lines.append('<br />\n')
            i += 1
            continue
        
        html_lines.append('<p>' + line.strip() + '</p>\n')
        i += 1
    
    return ''.join(html_lines)


def build_seo_page(md_path, html_path):
    """Convert a single SEO .md file to .html with wrapper."""
    with open(md_path) as f:
        md_content = f.read()
    
    with open(HEADER_FILE) as f:
        header = f.read()
    
    with open(FOOTER_FILE) as f:
        footer = f.read()
    
    # Extract frontmatter for meta tags
    title = 'ConfigForge Config File Converter | NaxiAI Devbench'
    description = 'Convert config files between JSON, YAML, TOML, XML, CSV, INI, .env, HCL, and .properties. 100% offline CLI tool with batch mode, type inference, and comment preservation.'
    og_title = 'ConfigForge — Multi-Format Config Converter'
    og_description = description
    
    fm_match = re.match(r'^---\n(.*?)\n---\n', md_content, re.DOTALL)
    if fm_match:
        fm = fm_match.group(1)
        title_match = re.search(r'title:\s*"(.+)"', fm)
        if title_match:
            title = title_match.group(1)
        desc_match = re.search(r'description:\s*"(.+)"', fm)
        if desc_match:
            description = desc_match.group(1)
        og_t = re.search(r'og_title:\s*"(.+)"', fm)
        if og_t:
            og_title = og_t.group(1)
        og_d = re.search(r'og_description:\s*"(.+)"', fm)
        if og_d:
            og_description = og_d.group(1)
    
    # Strip frontmatter, get body
    body_md = md_content
    if fm_match:
        body_md = md_content[fm_match.end():]
    
    # Convert markdown body to HTML
    body_html = markdown_to_html(body_md.strip())
    
    # Fix internal links (markdown files -> html)
    body_html = re.sub(r'href="([^"]+)\.md"', r'href="\1.html"', body_html)
    
    # Build full page
    extra_head = f'''
  <title>{title}</title>
  <meta name="description" content="{description}">
  <meta property="og:title" content="{og_title}">
  <meta property="og:description" content="{og_description}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="https://naxiai.com/tools/devbench/forge/seo/{os.path.basename(html_path)}">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{og_title}">
  <meta name="twitter:description" content="{og_description}">
'''
    
    full_html = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
{extra_head}{header}
  <main class="seo-page container">
    <div style="max-width:800px;margin:0 auto;padding:2rem 1rem;">
    {body_html}
    </div>
  </main>
{footer}
'''
    
    os.makedirs(os.path.dirname(html_path), exist_ok=True)
    with open(html_path, 'w') as f:
        f.write(full_html)
    
    word_count = len(body_md.split())
    return word_count


def main():
    os.makedirs(WEB_SEO_DST, exist_ok=True)
    
    total = 0
    count = 0
    for fname in sorted(os.listdir(FORGE_SEO_SRC)):
        if not fname.endswith('.md') or fname.startswith('_'):
            continue
        md_path = os.path.join(FORGE_SEO_SRC, fname)
        html_name = fname[:-3] + '.html'
        html_path = os.path.join(WEB_SEO_DST, html_name)
        
        try:
            wc = build_seo_page(md_path, html_path)
            total += wc
            count += 1
            print(f"  ✅ {html_name} ({wc} words)")
        except Exception as e:
            print(f"  ❌ {html_name}: {e}")
    
    print(f"\nTotal: {count} pages, {total} words converted to HTML")


if __name__ == '__main__':
    main()
