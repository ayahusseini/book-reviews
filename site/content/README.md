# Content

This module owns the source material that gets fed into the app.

The general flow is that once `import-posts` is run by the flask app `cli`, all markdown posts found (recursively) under some specified path should be:
- identified
- Parsed into a `MarkdownPost` object (including the frontmatter)
    - This is then upserted as a post into the SQLite3 database
    - And any quotes are extracted out into their own `Post` object (where appropriate)

This module is responsible for handling the creation of `MarkdownPost` objects. These objects are uniquely identified by a `slug`:
- Markdown posts have a slug that is pre-set by the user
    - If contents change on the next slug, but not the slug itself, then the post is updated rather than re-inserted 
- The quote-posts have a slug generated as the parent post slug + the quote hash