"""Per-rule lint modules.

Each module exports one or more ``check_*`` functions that take the
shared ``issues`` list plus whatever inputs the rule needs (the parsed
root, the schema, the chapter's path on disk, ...). Rules never log to
stdout and never raise on lint errors \u2014 they only append to ``issues``.
"""
