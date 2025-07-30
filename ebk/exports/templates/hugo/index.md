---
title: "{{ title }}"
type: "library-section"
layout: "list"
organize_by: "{{ organize_by }}"
group_key: "{{ group_key }}"
book_count: {{ book_count }}
---

# {{ title }}

This section contains **{{ book_count }} book{{ 's' if book_count != 1 else '' }}**.

## Books in this section

<div class="book-grid">
{%- for book in books %}
  <div class="book-card">
    {%- if book.cover_path %}
    <div class="book-cover-thumb">
      <a href="/library/{{ group_key }}/{{ book.slug }}/">
        <img src="/ebooks/{{ book.cover_path.split('/')[-1] }}" alt="{{ book.title }}" />
      </a>
    </div>
    {%- endif %}
    <div class="book-info">
      <h3><a href="/library/{{ group_key }}/{{ book.slug }}/">{{ book.title }}</a></h3>
      {%- if book.creators %}
      <p class="creators">{{ book.creators | join_list }}</p>
      {%- endif %}
      {%- if book.year %}
      <p class="year">{{ book.year }}</p>
      {%- endif %}
    </div>
  </div>
{%- endfor %}
</div>

## Browse by

<nav class="browse-nav">
  <ul>
    <li><a href="/library/">All Books</a></li>
    <li><a href="/library/year/">By Year</a></li>
    <li><a href="/library/language/">By Language</a></li>
    <li><a href="/library/subject/">By Subject</a></li>
    <li><a href="/library/creator/">By Creator</a></li>
  </ul>
</nav>