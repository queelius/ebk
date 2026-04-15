---
title: "{{ title }}"
type: "library"
layout: "library-home"
total_books: {{ stats.total_books }}
total_creators: {{ stats.total_creators }}
total_subjects: {{ stats.total_subjects }}
---

# {{ title }}

Welcome to the library. This collection contains **{{ stats.total_books }} books** by **{{ stats.total_creators }} creators** covering **{{ stats.total_subjects }} subjects**.

## Library Statistics

<div class="library-stats">
  <div class="stat-card">
    <h3>{{ stats.total_books }}</h3>
    <p>Total Books</p>
  </div>
  <div class="stat-card">
    <h3>{{ stats.total_creators }}</h3>
    <p>Authors</p>
  </div>
  <div class="stat-card">
    <h3>{{ stats.total_subjects }}</h3>
    <p>Subjects</p>
  </div>
  <div class="stat-card">
    <h3>{{ stats.languages | length }}</h3>
    <p>Languages</p>
  </div>
</div>

## Browse Library

<div class="browse-options">
  <div class="browse-card">
    <h3><a href="/library/year/">By Year</a></h3>
    <p>Browse books organized by publication year</p>
  </div>
  <div class="browse-card">
    <h3><a href="/library/creator/">By Author</a></h3>
    <p>Find books by your favorite authors</p>
  </div>
  <div class="browse-card">
    <h3><a href="/library/subject/">By Subject</a></h3>
    <p>Explore books by topic and genre</p>
  </div>
  <div class="browse-card">
    <h3><a href="/library/language/">By Language</a></h3>
    <p>Filter books by language</p>
  </div>
</div>

{%- if stats.top_creators %}
## Top Authors

<ol class="top-list">
{%- for creator, count in stats.top_creators %}
  <li>
    <a href="/library/creator/{{ creator | slugify }}/">{{ creator }}</a>
    <span class="count">({{ count }} book{{ 's' if count != 1 else '' }})</span>
  </li>
{%- endfor %}
</ol>
{%- endif %}

{%- if stats.top_subjects %}
## Popular Subjects

<div class="tag-cloud">
{%- for subject, count in stats.top_subjects %}
  <a href="/library/subject/{{ subject | slugify }}/" 
     class="tag tag-{{ 'large' if count > 10 else 'medium' if count > 5 else 'small' }}">
    {{ subject }} ({{ count }})
  </a>
{%- endfor %}
</div>
{%- endif %}

## Recent Additions

<div class="recent-books">
{%- for book in books[:10] %}
  <div class="book-item">
    <h4><a href="/library/{{ book.slug }}/">{{ book.title }}</a></h4>
    {%- if book.creators %}
    <p class="creators">by {{ book.creators | join_list }}</p>
    {%- endif %}
  </div>
{%- endfor %}
</div>

## Search

<div class="search-box">
  <form action="/search/" method="get">
    <input type="text" name="q" placeholder="Search books..." />
    <button type="submit">Search</button>
  </form>
</div>

---

<div class="library-footer">
  <p>This library is powered by <a href="https://github.com/queelius/ebk">ebk</a></p>
</div>