# MML2OMML.xsl attribution

`mml2omml.xsl` is the MathML → Office MathML (OMML) XSLT 1.0 stylesheet
that ships with Microsoft Office. The same stylesheet is also part of the
Text Encoding Initiative (TEI) "XSL stylesheets for TEI XML" project,
which is published under the
[BSD-2-Clause](https://opensource.org/licenses/BSD-2-Clause) license.

We redistribute the stylesheet verbatim. It is loaded at runtime by
`docx/math.py` to convert LaTeX (via `latex2mathml`) into Word's native
equation format so that `<rd-math>` blocks round-trip into editable
equations on Confluence import.

Upstream sources:

- TEI Stylesheets — https://github.com/TEIC/Stylesheets
- A widely-mirrored copy of the same file lives at
  https://github.com/lavakumarThatisetti/Extracting-Math-formulas-using-Apache-poi-in-java/blob/master/MML2OMML.XSL
