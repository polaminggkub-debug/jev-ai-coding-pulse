"""Shared navigation for the three published pages."""


def nav(current):
    pages = (("index.html", "Rankings"), ("reads.html", "Worth reading"),
             ("sources.html", "Sources &amp; communities"))
    links = []
    for href, label in pages:
        active = ' aria-current="page"' if href == current else ''
        links.append(f'<a href="{href}"{active}>{label}</a>')
    return '<nav class="page-nav" aria-label="Pulse pages">' + ''.join(links) + '</nav>'
