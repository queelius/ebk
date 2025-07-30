---
title: "{{ book.title }}"
date: {{ book.date | default_if_none('') }}
draft: false
type: "book"
unique_id: "{{ book.unique_id }}"

# Creators
creators: {{ book.creators | tojson }}
{%- if book.creators %}
creators_display:
{%- for creator in book.creators %}
  - "{{ creator }}"
{%- endfor %}
{%- endif %}

# Subjects and Classification
{%- if book.subjects %}
subjects: {{ book.subjects | tojson }}
tags:
{%- for subject in book.subjects %}
  - "{{ subject | slugify }}"
{%- endfor %}
{%- endif %}

# Language and Publishing
language: "{{ book.language }}"
{%- if book.publisher %}
publisher: "{{ book.publisher }}"
{%- endif %}
{%- if book.year %}
year: "{{ book.year }}"
{%- endif %}

# Identifiers
{%- if book.identifiers %}
identifiers:
{%- for key, value in book.identifiers.items() %}
  {{ key }}: "{{ value }}"
{%- endfor %}
{%- endif %}

# Files
{%- if ebook_urls %}
ebook_files:
{%- for url in ebook_urls %}
  - "{{ url }}"
{%- endfor %}
{%- endif %}
{%- if cover_url %}
cover_image: "{{ cover_url }}"
{%- endif %}

# Description
{%- if book.description %}
description: |
  {{ book.description | indent(2) }}
{%- endif %}
---

# {{ book.title }}

{%- if book.creators %}
**By {{ book.creators | join_list }}**
{%- endif %}

{%- if cover_url %}
<div class="book-cover">
  <img src="{{ cover_url }}" alt="Cover of {{ book.title }}" />
</div>
{%- endif %}

## Details

<div class="book-metadata">
  <dl>
    {%- if book.creators %}
    <dt>Author(s)</dt>
    <dd>{{ book.creators | join_list }}</dd>
    {%- endif %}
    
    {%- if book.publisher %}
    <dt>Publisher</dt>
    <dd>{{ book.publisher }}</dd>
    {%- endif %}
    
    {%- if book.date %}
    <dt>Publication Date</dt>
    <dd>{{ book.date }}</dd>
    {%- endif %}
    
    {%- if book.language %}
    <dt>Language</dt>
    <dd>{{ book.language }}</dd>
    {%- endif %}
    
    {%- if book.subjects %}
    <dt>Subjects</dt>
    <dd>
      <ul class="subject-list">
      {%- for subject in book.subjects %}
        <li><a href="/library/subject/{{ subject | slugify }}/">{{ subject }}</a></li>
      {%- endfor %}
      </ul>
    </dd>
    {%- endif %}
    
    {%- if book.identifiers %}
    <dt>Identifiers</dt>
    <dd>
      <ul class="identifier-list">
      {%- for key, value in book.identifiers.items() %}
        <li><strong>{{ key }}:</strong> {{ value }}</li>
      {%- endfor %}
      </ul>
    </dd>
    {%- endif %}
  </dl>
</div>

{%- if book.description %}
## Description

{{ book.description }}
{%- endif %}

{%- if ebook_urls %}
## Download

<div class="download-section">
{%- for url in ebook_urls %}
  {%- set filename = url.split('/')[-1] %}
  {%- set extension = filename.split('.')[-1].upper() %}
  <a href="{{ url }}" class="download-button download-{{ extension | lower }}">
    Download {{ extension }}
  </a>
{%- endfor %}
</div>
{%- endif %}

---

<div class="book-navigation">
  <a href="/library/">← Back to Library</a>
  {%- if book.creators %}
  {%- for creator in book.creators %}
  | <a href="/library/creator/{{ creator | slugify }}/">More by {{ creator }}</a>
  {%- endfor %}
  {%- endif %}
</div>