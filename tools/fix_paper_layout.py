#!/usr/bin/env python3
"""Format the latest Paper 03 source without rewriting its narrative or results.

The input snapshot preserves the uploaded text with source whitespace reflowed.
The output is a single, self-contained .tex file for the existing Overleaf assets.
"""
from __future__ import annotations
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / 'revisions/20261008_layout_input.tex'
OUTPUT = ROOT / 'MTT_reveyrand_updated.tex'
REPORT = ROOT / 'LAYOUT_CHECK.md'
source = INPUT.read_text(encoding='utf-8')
text = source
changes: list[str] = []


def active(s: str) -> str:
    return re.sub(r'(?m)(?<!\\)%[^\n]*', '', s)


def compact(s: str) -> str:
    return re.sub(r'\s+', '', s)


def replace_once(old: str, new: str, title: str) -> None:
    global text
    if text.count(old) != 1:
        raise ValueError(f'{title}: expected one exact target, found {text.count(old)}')
    text = text.replace(old, new, 1)
    changes.append(title)


# Preserve all author-written text. These settings change layout only.
settings = r'''
% -------- Layout only: readable columns and less deferred float backlog --------
\usepackage{microtype}
\usepackage{tabularx}
\setcounter{topnumber}{4}
\setcounter{bottomnumber}{3}
\setcounter{totalnumber}{6}
\setcounter{dbltopnumber}{3}
\renewcommand{\topfraction}{0.92}
\renewcommand{\bottomfraction}{0.85}
\renewcommand{\textfraction}{0.06}
\renewcommand{\floatpagefraction}{0.60}
\renewcommand{\dbltopfraction}{0.92}
\renewcommand{\dblfloatpagefraction}{0.60}
\setlength{\floatsep}{8pt plus 2pt minus 2pt}
\setlength{\textfloatsep}{10pt plus 2pt minus 2pt}
\setlength{\intextsep}{8pt plus 2pt minus 2pt}
\setlength{\dblfloatsep}{8pt plus 2pt minus 2pt}
\setlength{\dbltextfloatsep}{10pt plus 2pt minus 2pt}
\setlength{\emergencystretch}{1.5em}
\makeatletter
% Do not vertically centre, or widely separate, floats on float-only pages.
\setlength{\@fptop}{0pt}
\setlength{\@fpsep}{10pt plus 2pt minus 2pt}
\setlength{\@fpbot}{0pt plus 1fil}
\setlength{\@dblfptop}{0pt}
\setlength{\@dblfpsep}{10pt plus 2pt minus 2pt}
\setlength{\@dblfpbot}{0pt plus 1fil}
\makeatother
\AtBeginDocument{%
  \raggedbottom
  \setlength{\abovedisplayskip}{7pt plus 1pt minus 2pt}%
  \setlength{\belowdisplayskip}{7pt plus 1pt minus 2pt}%
  \setlength{\abovedisplayshortskip}{3pt plus 1pt}%
  \setlength{\belowdisplayshortskip}{5pt plus 1pt minus 1pt}%
}
% ---------------------------------------------------------------------------
'''
replace_once(r'\begin{document}', settings + '\n' + r'\begin{document}',
             'Added bounded spacing and flexible float-page settings; retained body font size and page geometry.')

# Top-only floats delay the entire float queue. Permit text and float-only pages.
text = re.sub(r'(\\begin\{(?:figure|table)\*\})\[!t\]', r'\1[!tbp]', text)
text = re.sub(r'(\\begin\{(?:figure|table)\})\[!t\]', r'\1[!htbp]', text)
text = text.replace(r'\begin{algorithm}[t]', r'\begin{algorithm}[!tbp]')
changes.append('Allowed top/bottom/float-page placement; allowed in-text placement for single-column figures and tables.')

# The earlier barrier was immediately after Results D and could split the final prose.
replace_once('% Flush all pending result floats before the conclusion so that\n% figures and tables do not drift into the references.\n\\FloatBarrier\n',
             '% Conclusion and declarations continue without an intermediate float flush.\n',
             'Removed the float barrier between Results D and Conclusion.')
# Keep exactly one boundary at the bibliography, not a forced new page.
if text.count(r'\FloatBarrier') != 1:
    raise AssertionError('Expected exactly one final bibliography float barrier.')
changes.append('Kept one FloatBarrier immediately before the bibliography; all declarations remain before References.')

# Reflow mathematical statements using their original symbols and values.
# Every replacement retains one numbered equation and every original label.
eq_re = re.compile(r'\\begin\{equation\}(.*?)\\end\{equation\}', re.S)
reflows: dict[str, str] = {}


def register(marker: str, body: str) -> None:
    key = compact(marker)
    if key in reflows:
        raise ValueError('Duplicate equation marker')
    reflows[key] = body.strip()


register(r'\label{eq:overall_framework}', r'''
\begin{aligned}
\widehat{\mathbf{R}}
&=\mathcal{S}_{\mathrm{VBI}}\left[\mathcal{T}_{\mathrm{TB}}\left(\widehat{\mathbf{Y}}\right)\right],\\
\widehat{\mathbf{Y}}
&=\mathcal{F}_{\mathrm{tr}}\left(\mathbf{X}_{\mathrm{obs}}\right),
\end{aligned}
''')
register(r'\label{eq:mean_vehicle_speed}', r'''
\begin{aligned}
V_{\ell,s}(t)&=\frac{1}{O_{\ell,s}(t)}\sum_{i\in\mathcal{V}_{\ell,s}(t)}v_i(t),\\
&\qquad O_{\ell,s}(t)>0,
\end{aligned}
''')
register(r'\label{eq:mean_vehicle_type}', r'''
\begin{aligned}
C_{\ell,s}(t)&=\frac{1}{O_{\ell,s}(t)}\sum_{i\in\mathcal{V}_{\ell,s}(t)}c_i,\\
&\qquad O_{\ell,s}(t)>0,
\end{aligned}
''')
register(r'\label{eq:lane_cell_state}', r'''
\begin{aligned}
\mathbf{Y}_{\ell,s}(t)
&=\Bigl[O_{\ell,s}(t),\,V_{\ell,s}(t),\\
&\qquad P_{\ell,s}(t),\,C_{\ell,s}(t)\Bigr]^{T},
\end{aligned}
''')
register(r'\mathcal{V}_{t+\tau}^{\mathrm{phy}} =', r'''
\begin{aligned}
\mathcal{V}_{t+\tau}^{\mathrm{phy}}
&=\Phi_{\mathrm{phy}}\left(\mathcal{V}_{t+\tau-1}^{\mathrm{phy}}\right),\\
&\qquad \tau=1,\ldots,T_{\mathrm{pred}},
\end{aligned}
''')
register(r'M_{t+\tau}^{\mathrm{phy}} =', r'''
\begin{aligned}
M_{t+\tau}^{\mathrm{phy}}
&=\mathcal{R}\left(\mathcal{V}_{t+\tau}^{\mathrm{phy}}\right),\\
&\qquad \tau=1,\ldots,T_{\mathrm{pred}},
\end{aligned}
''')
register(r'Y^{\mathrm{phy}} = \left[', r'''
\begin{aligned}
Y^{\mathrm{phy}}
&=\Bigl[M_{t+1}^{\mathrm{phy}},M_{t+2}^{\mathrm{phy}},\\
&\qquad\ldots,M_{t+T_{\mathrm{pred}}}^{\mathrm{phy}}\Bigr].
\end{aligned}
''')
register(r'\mathcal{L}_{\mathrm{data}} =', r'''
\begin{aligned}
\mathcal{L}_{\mathrm{data}}
&=\frac{1}{|\Omega|}\sum_{(\tau,l,s,c)\in\Omega}\omega_c\\
&\qquad\times\bigl(\widehat{M}_{\tau,l,s,c}-M_{\tau,l,s,c}\bigr)^2,
\end{aligned}
''')
register(r'\mathcal{L}_{\mathrm{phy}} =', r'''
\begin{aligned}
\mathcal{L}_{\mathrm{phy}}
&=\frac{1}{|\Omega|}\sum_{(\tau,l,s,c)\in\Omega}\\
&\qquad\bigl(\widehat{M}_{\tau,l,s,c}-M_{\tau,l,s,c}^{\mathrm{phy}}\bigr)^2.
\end{aligned}
''')
register(r'\mathcal{L}_{\mathrm{occ}} =', r'''
\begin{aligned}
\mathcal{L}_{\mathrm{occ}}
&=-\frac{1}{N}\sum_{\tau,l,s}\Bigl[\\
&\qquad\lambda_{+}B_{\tau,l,s}\log p_{\tau,l,s}^{\mathrm{occ}}\\
&\qquad+(1-B_{\tau,l,s})\log(1-p_{\tau,l,s}^{\mathrm{occ}})\Bigr],
\end{aligned}
''')
register(r'\mathcal{L}_{\mathrm{empty}} =', r'''
\begin{aligned}
\mathcal{L}_{\mathrm{empty}}
&=\frac{1}{N}\sum_{\tau,l,s}(1-B_{\tau,l,s})\\
&\qquad\times\bigl(\widehat{M}_{\tau,l,s}^{(w)}\bigr)^2.
\end{aligned}
''')
register(r'\mathcal{L}_{\mathrm{load}} =', r'''
\begin{aligned}
\mathcal{L}_{\mathrm{load}}
&=\frac{1}{T_{\mathrm{pred}}S}\sum_{\tau=1}^{T_{\mathrm{pred}}}\sum_{s=1}^{S}\\
&\qquad\bigl(\widehat{P}_{s}(t+\tau)-P_s(t+\tau)\bigr)^2.
\end{aligned}
''')
register(r'\mathcal{J} =', r'''
\begin{aligned}
\mathcal{J}
&=\lambda_{\mathrm{data}}\mathcal{L}_{\mathrm{data}}
 +\lambda_{\mathrm{phy}}\mathcal{L}_{\mathrm{phy}}\\
&\quad+\lambda_{\mathrm{occ}}\mathcal{L}_{\mathrm{occ}}
 +\lambda_{\mathrm{empty}}\mathcal{L}_{\mathrm{empty}}\\
&\quad+\lambda_{\mathrm{load}}\mathcal{L}_{\mathrm{load}},
\end{aligned}
''')
register(r'\label{eq:traffic_cell_center}', r'''
\begin{aligned}
x_s^{\mathrm{tr}}&=\left(s-\frac{1}{2}\right)\frac{L_{\mathrm{tr}}}{S},\\
&\qquad s=1,\ldots,S,
\end{aligned}
''')
register(r'P_{\ell,s}(t) = \left[1-', r'''
\begin{aligned}
P_{\ell,s}(t)
&=\bigl[1-\alpha(t)\bigr]P_{\ell,s}(t_k)\\
&\quad+\alpha(t)P_{\ell,s}(t_{k+1}).
\end{aligned}
''')
register(r'\mathcal{L}=T-U=', r'''
\begin{aligned}
\mathcal{L}&=T-U\\
&=\left(T_b+\sum_i T_{v,i}\right)\\
&\quad-\left(U_b+\sum_i U_{s,i}\right),
\end{aligned}
''')
register(r'=\sum_{i\in\mathcal{A}(t)}F_i(t)', r'''
\begin{aligned}
&\mu_b\frac{\partial^2 w(x,t)}{\partial t^2}
 +EI\frac{\partial^4 w(x,t)}{\partial x^4}\\
&\qquad=\sum_{i\in\mathcal{A}(t)}F_i(t)
 \delta_{\mathrm{D}}\bigl(x-x_i(t)\bigr),
\end{aligned}
''')
register(r'M_r\ddot{q}_r(t)+', r'''
\begin{aligned}
M_r\ddot{q}_r(t)+C_r\dot{q}_r(t)+K_rq_r(t)&=Q_r(t),\\
& r=1,\ldots,N_m,
\end{aligned}
''')
register(r'\mathbf{M}(t)\ddot{\mathbf{u}}(t)+', r'''
\begin{aligned}
&\mathbf{M}(t)\ddot{\mathbf{u}}(t)
 +\mathbf{C}(t)\dot{\mathbf{u}}(t)\\
&\qquad+\mathbf{K}(t)\mathbf{u}(t)=\mathbf{f}(t),
\end{aligned}
''')
register(r'\mathrm{RMSE}_{\mathrm{global}}=', r'''
\begin{aligned}
\mathrm{RMSE}_{\mathrm{global}}
&=\Biggl[\frac{1}{T_{\mathrm{pred}}LSN_c}
 \sum_{\tau=1}^{T_{\mathrm{pred}}}\sum_{l=1}^{L}\\
&\qquad\sum_{s=1}^{S}\sum_{c=1}^{N_c}
 \bigl(\widehat{M}_{\tau,l,s,c}-M_{\tau,l,s,c}\bigr)^2\Biggr]^{1/2}.
\end{aligned}
''')
register(r'\mathrm{RMSE}_{\mathrm{occ}}=', r'''
\begin{aligned}
\mathrm{RMSE}_{\mathrm{occ}}
&=\Biggl[\frac{1}{|\Omega_{\mathrm{occ}}|}
 \sum_{(\tau,l,s,c)\in\Omega_{\mathrm{occ}}}\\
&\qquad\bigl(\widehat{M}_{\tau,l,s,c}-M_{\tau,l,s,c}\bigr)^2\Biggr]^{1/2},
\end{aligned}
''')
register(r'\mathrm{RMSE}_{\mathrm{load}}=', r'''
\begin{aligned}
\mathrm{RMSE}_{\mathrm{load}}
&=\Biggl[\frac{1}{T_{\mathrm{pred}}LS}
 \sum_{\tau=1}^{T_{\mathrm{pred}}}\sum_{l=1}^{L}\sum_{s=1}^{S}\\
&\qquad\bigl(\widehat{P}_{\tau,l,s}-P_{\tau,l,s}\bigr)^2\Biggr]^{1/2}.
\end{aligned}
''')
register(r'\mathrm{RMSE}_{\mathrm{total}}=', r'''
\begin{aligned}
\mathrm{RMSE}_{\mathrm{total}}
&=\Biggl\{\frac{1}{T_{\mathrm{pred}}}
 \sum_{\tau=1}^{T_{\mathrm{pred}}}\\
&\quad\Biggl[\sum_{l=1}^{L}\sum_{s=1}^{S}\widehat{P}_{\tau,l,s}\\
&\qquad-\sum_{l=1}^{L}\sum_{s=1}^{S}P_{\tau,l,s}\Biggr]^2\Biggr\}^{1/2}.
\end{aligned}
''')
register(r'\mathrm{RMSE}_{u}(\xi)=', r'''
\begin{aligned}
\mathrm{RMSE}_{u}(\xi)
&=\Biggl[\frac{1}{N_t}\sum_{n=1}^{N_t}\\
&\quad\bigl(\widehat{u}(\xi,t_n)-u^{\mathrm{ref}}(\xi,t_n)\bigr)^2\Biggr]^{1/2}.
\end{aligned}
''')
register(r'\mathrm{RMSE}_{a}=', r'''
\begin{aligned}
\mathrm{RMSE}_{a}
&=\Biggl\{\frac{1}{N_t}\sum_{n=1}^{N_t}
 \Biggl[\widehat{\ddot{u}}\left(\frac{L_b}{2},t_n\right)\\
&\qquad-\ddot{u}^{\mathrm{ref}}\left(\frac{L_b}{2},t_n\right)
 \Biggr]^2\Biggr\}^{1/2},
\end{aligned}
''')
register(r'\mathrm{MAE}_{\mathrm{peak}}', r'''
\begin{aligned}
\mathrm{MAE}_{\mathrm{peak}}
&=\frac{1}{N_{\mathrm{test}}}\sum_{j=1}^{N_{\mathrm{test}}}\\
&\quad\Biggl|\max_n\left|\widehat{u}_j\left(\frac{L_b}{2},t_n\right)\right|\\
&\qquad-\max_n\left|u_j^{\mathrm{ref}}\left(\frac{L_b}{2},t_n\right)\right|\Biggr|.
\end{aligned}
''')

hits = Counter()

def format_eq(match: re.Match[str]) -> str:
    old = match.group(1)
    labels = re.findall(r'\\label\{[^}]+\}', old)
    found = [key for key in reflows if key in compact(old)]
    if len(found) > 1:
        raise ValueError(f'Ambiguous equation markers: {found}')
    if not found:
        return match.group(0)
    key = found[0]
    hits[key] += 1
    return '\\begin{equation}\n' + reflows[key] + '\n' + '\n'.join(labels) + '\n\\end{equation}'

text = eq_re.sub(format_eq, text)
if set(hits) != set(reflows) or any(n != 1 for n in hits.values()):
    raise AssertionError(f'Equation replacement mismatch: {hits}; missing {set(reflows)-set(hits)}')
changes.append(f'Reflowed {len(hits)} wide equations; retained equation count, labels, variables, and numerical results.')

# Break long algorithm assignments. The argument sequence remains unchanged.
call1 = r'$\mathbf{s}_{VBI}\leftarrow\operatorname{Newmark}(\mathbf{M},\mathbf{C},\mathbf{K},\mathbf{f},\mathbf{s}_{VBI},\Delta t_s,\beta,\gamma)$'
call2 = r'''$\begin{aligned}[t]
&\mathbf{s}_{VBI}\leftarrow\operatorname{Newmark}(\mathbf{M},\mathbf{C},\mathbf{K},\mathbf{f},\\
&\qquad\mathbf{s}_{VBI},\Delta t_s,\beta,\gamma)
\end{aligned}$'''
if text.count(call1) != 2:
    raise AssertionError('Expected two Newmark algorithm calls')
text = text.replace(call1, call2)
for rhs in [r'\mathcal{A}(\mathbf{P}^{*},\mathbf{h}^{*},\mathbf{F}^{*};\Theta_b,\Theta_v)',
            r'\mathcal{A}(\widehat{\mathbf{P}}^{*},\widehat{\mathbf{h}}^{*},\widehat{\mathbf{F}}^{*};\Theta_b,\Theta_v)']:
    old = r'$(\mathbf{M},\mathbf{C},\mathbf{K},\mathbf{f})\leftarrow' + rhs + '$'
    new = (r'$\begin{aligned}[t]&(\mathbf{M},\mathbf{C},\mathbf{K},\mathbf{f})\leftarrow'
           + '\\\\\n&\quad ' + rhs + r'\end{aligned}$')
    replace_once(old, new, 'Wrapped an algorithm matrix-assembly call without changing its arguments.')
replace_once(
    r'$\mathbf{z}_{i}^{\mathrm{phy}}\leftarrow[x_i^{+},\,l_i^{+},\,v_i^{+},\,w_i,\,c_i]^{T}$',
    r'''$\begin{aligned}[t]&\mathbf{z}_{i}^{\mathrm{phy}}\leftarrow\\
&\quad[x_i^{+},\,l_i^{+},\,v_i^{+},\,w_i,\,c_i]^{T}\end{aligned}$''',
    'Wrapped the vehicle-state assignment in Algorithm 1.')
replace_once(
    r'\Return{$w(L_b/4,t),\,w(L_b/2,t),\,w(3L_b/4,t),\,\ddot w(L_b/2,t)$}',
    r'''\Return{$\begin{aligned}[t]&w(L_b/4,t),\,w(L_b/2,t),\\
& w(3L_b/4,t),\,\ddot w(L_b/2,t)\end{aligned}$}''',
    'Wrapped Algorithm 2 return values without deleting any output.')
# Local indentation and display spacing prevent needless width/height pressure.
text = text.replace(r'\begin{algorithm}[!tbp]',
                    '\\begin{algorithm}[!tbp]\n\\SetInd{0.35em}{0.65em}\n'
                    '\\setlength{\\abovedisplayskip}{3pt}\n\\setlength{\\belowdisplayskip}{3pt}')
changes.append('Reduced algorithm indentation and internal display gaps; preserved all algorithm steps.')

# Use the same real font size in both wide results tables, without resizebox scaling.
float_re = re.compile(r'\\begin\{(figure\*?|table\*?)\}(?:\[[^]]*\])?.*?\\end\{\1\}', re.S)

def format_table(m: re.Match[str]) -> str:
    block = m.group(0)
    if 'tab:traffic_performance' in block or 'tab:bridge_response_performance' in block:
        block = block.replace(r'\scriptsize', r'\footnotesize')
        block = block.replace('\\resizebox{\\textwidth}{!}{%\n', '')
        spec = 'lccccccc' if 'tab:bridge_response_performance' in block else 'lcccccc'
        block = block.replace('\\begin{tabular}{' + spec + '}',
                              '\\begin{tabular*}{\\textwidth}{@{\\extracolsep{\\fill}}' + spec + '@{}}')
        block = block.replace('\\end{tabular}%\n}', r'\end{tabular*}')
    elif 'tab:dataset_configuration' in block:
        block = block.replace(r'\begin{tabular}{ll}',
                              r'\begin{tabularx}{\columnwidth}{@{}l>{\raggedright\arraybackslash}X@{}}')
        block = block.replace(r'\end{tabular}', r'\end{tabularx}')
    return block

text = float_re.sub(format_table, text)
changes.append('Matched Table II and Table III font size and booktabs rules; removed independent resizebox scaling.')
changes.append('Made Table I fit the column using a wrapping second column.')

# Give the existing result floats more text runway without changing their order.
# Move only float environments, never author-written paragraphs.
def detach_float(label: str) -> str:
    global text
    matches = [m for m in float_re.finditer(text) if '\\label{' + label + '}' in m.group(0)]
    if len(matches) != 1:
        raise ValueError(f'Cannot isolate float {label}')
    m = matches[0]
    block = m.group(0)
    text = text[:m.start()] + text[m.end():]
    return block

traffic_plots = [detach_float(k) for k in [
    'fig:predicted_total_load', 'fig:horizon_load_rmse',
    'fig:traffic_metric_comparison', 'fig:spatiotemporal_load_fields']]
anchor = r'\label{sec:traffic_results}'
replace_once(anchor, anchor + '\n\n' + '\n\n'.join(traffic_plots),
             'Released the four traffic-results figures at the start of their subsection, before its discussion.')
structural_plots = [detach_float(k) for k in [
    'fig:representative_bridge_response', 'fig:bridge_response_metrics',
    'fig:bridge_error_distribution', 'fig:traffic_bridge_error_relationship',
    'fig:support_consistency_effect']]
anchor = r'\label{sec:bridge_response_results}'
replace_once(anchor, anchor + '\n\n' + '\n\n'.join(structural_plots),
             'Released the structural figures before their result paragraphs; preserved figure order and captions.')

# Standardise only nonbreaking spaces before references; no narrative rewriting.
text = text.replace('Fig. \\ref{', 'Fig.~\\ref{')
text = re.sub(r'\n{4,}', '\n\n\n', text)

# Structural source checks.
a0, a1 = active(source), active(text)
labels0 = re.findall(r'\\label\{([^}]+)\}', a0)
labels1 = re.findall(r'\\label\{([^}]+)\}', a1)
refs1 = re.findall(r'\\(?:ref|eqref)\{([^}]+)\}', a1)
assert Counter(labels0) == Counter(labels1), 'A label changed or disappeared'
assert len(labels1) == len(set(labels1)), 'Duplicate labels'
assert not (set(refs1) - set(labels1)), 'Missing reference targets'
assert len(eq_re.findall(a0)) == len(eq_re.findall(a1)), 'Equation count changed'
assert Counter(re.findall(r'\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}', a0)) == Counter(re.findall(r'\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}', a1)), 'An image changed'
assert re.findall(r'\\cite\{([^}]+)\}', a0) == re.findall(r'\\cite\{([^}]+)\}', a1), 'Citation keys changed'

# Compare all narrative outside numbered equations and float/algorithm environments.
def narrative(s: str) -> str:
    s = active(s).split(r'\begin{document}', 1)[1]
    s = eq_re.sub('', s)
    s = re.sub(r'\\begin\{(figure\*?|table\*?|algorithm)\}(?:\[[^]]*\])?.*?\\end\{\1\}', '', s, flags=re.S)
    s = s.replace(r'\FloatBarrier', '').replace('Fig.~', 'Fig. ')
    return re.sub(r'\s+', ' ', s).strip()
assert narrative(source) == narrative(text), 'Narrative preservation check failed'

# Check every table entry, every caption and the source order of all figures.
def float_map(s: str) -> dict[str, str]:
    out = {}
    for m in float_re.finditer(active(s)):
        label = re.search(r'\\label\{([^}]+)\}', m.group(0))
        if label:
            out[label.group(1)] = m.group(0)
    return out
f0, f1 = float_map(source), float_map(text)
assert set(f0) == set(f1)
for label, block in f0.items():
    if label.startswith('tab:'):
        nums = lambda b: re.findall(r'(?<![A-Za-z])[-+]?\d+(?:\.\d+)?', b.split(r'\toprule', 1)[1])
        assert nums(block) == nums(f1[label]), f'Table values changed: {label}'
    # All caption source text remains verbatim apart from whitespace.
    start = block.index(r'\caption{')
    end = block.index(r'\label{', start)
    start1 = f1[label].index(r'\caption{')
    end1 = f1[label].index(r'\label{', start1)
    assert compact(block[start:end]) == compact(f1[label][start1:end1]), f'Caption changed: {label}'

figlabels = lambda s: [re.search(r'\\label\{([^}]+)\}', m.group(0)).group(1) for m in float_re.finditer(active(s)) if m.group(1).startswith('figure')]
assert figlabels(source) == figlabels(text), 'Figure numbering order changed'
assert a1.count(r'\end{document}') == 1
assert text.count(r'\FloatBarrier') == 1
bib = text.index(r'\bibliography{Ref}')
assert text.index(r'\FloatBarrier') < text.index(r'\bibliographystyle{IEEEtran}') < bib
assert active(text[bib + len(r'\bibliography{Ref}'):]).strip() == r'\end{document}', 'Content after bibliography'
assert not re.search(r'\\begin\{(?:figure\*?|table\*?|algorithm)\}', text[bib:])

OUTPUT.write_text(text, encoding='utf-8')
checks = {
    'narrative_unchanged': True,
    'abstract_title_introduction_conclusion_declarations_unchanged': True,
    'equation_count': len(eq_re.findall(a1)),
    'wide_equations_reflowed': len(hits),
    'table_values_unchanged': True,
    'figure_files_captions_order_unchanged': True,
    'citation_keys_unchanged': True,
    'missing_internal_references': [],
    'duplicate_labels': [],
    'bibliography_is_last': True,
    'final_float_barriers': 1,
    'input_snapshot_sha256': hashlib.sha256(source.encode()).hexdigest(),
    'output_sha256': hashlib.sha256(text.encode()).hexdigest(),
}
(ROOT / 'revisions/20261008_layout_checks.json').write_text(json.dumps(checks, indent=2) + '\n')
REPORT.write_text('# Layout-only revision\n\n'
                 'Source: the latest uploaded `MTT_reveyrand_updated (3) (3).tex`.\n'
                 'The input snapshot normalises source whitespace, not the rendered wording.\n\n'
                 '## Changes\n' + '\n'.join('- ' + c for c in changes) + '\n\n'
                 '## Preservation checks\n```json\n' + json.dumps(checks, indent=2) + '\n```\n\n'
                 '## Validation limits\n'
                 'The repository does not contain the figure assets or Ref.bib.\n'
                 'A complete paper PDF and its final page gaps cannot be verified from this repository alone.\n'
                 'No solver formulas, traffic parameters, empirical values, or scientific claims were changed.\n'
                 'Natural page-end whitespace depends on the actual figures and bibliography.\n'
                 'The remaining FloatBarrier drains pending floats before the bibliography.\n', encoding='utf-8')
print(json.dumps(checks, indent=2))
