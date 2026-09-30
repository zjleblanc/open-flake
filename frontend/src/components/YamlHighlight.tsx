import './YamlHighlight.css';

type YamlTokenType =
  'plain' | 'comment' | 'key' | 'module' | 'string' | 'number' | 'boolean' | 'punctuation';

interface YamlToken {
  text: string;
  type: YamlTokenType;
}

/** Ansible fully-qualified collection module names, e.g. `servicenow.itsm.incident`. */
const MODULE_NAME_RE = /^[\w-]+(\.[\w-]+){2,}$/;
const KEY_RE = /^([A-Za-z0-9_.-]+):(\s|$)/;
const LIST_MARKER_RE = /^(-\s+)/;
const BOOLEAN_RE = /^(true|false|yes|no|null|~)$/i;
const NUMBER_RE = /^-?\d+(\.\d+)?$/;

/** Finds the start of a trailing `#` comment, ignoring `#` inside quoted strings. */
function findCommentStart(text: string): number {
  let inSingle = false;
  let inDouble = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (ch === "'" && !inDouble) {
      inSingle = !inSingle;
    } else if (ch === '"' && !inSingle) {
      inDouble = !inDouble;
    } else if (ch === '#' && !inSingle && !inDouble && (i === 0 || /\s/.test(text[i - 1]))) {
      return i;
    }
  }
  return -1;
}

function tokenizeValue(value: string): YamlToken[] {
  if (value === '') return [];
  const trimmed = value.trim();
  if (BOOLEAN_RE.test(trimmed)) return [{ text: value, type: 'boolean' }];
  if (NUMBER_RE.test(trimmed)) return [{ text: value, type: 'number' }];
  return [{ text: value, type: 'string' }];
}

/** Tokenizes a single line of YAML into typed spans for lightweight syntax highlighting. */
function tokenizeLine(line: string): YamlToken[] {
  const tokens: YamlToken[] = [];

  const indentMatch = line.match(/^(\s*)/);
  const indent = indentMatch ? indentMatch[1] : '';
  let rest = line.slice(indent.length);
  if (indent) tokens.push({ text: indent, type: 'plain' });

  if (rest === '') return tokens;

  if (rest.startsWith('#')) {
    tokens.push({ text: rest, type: 'comment' });
    return tokens;
  }

  if (rest === '-') {
    tokens.push({ text: rest, type: 'punctuation' });
    return tokens;
  }

  const listMatch = rest.match(LIST_MARKER_RE);
  if (listMatch) {
    tokens.push({ text: listMatch[1], type: 'punctuation' });
    rest = rest.slice(listMatch[1].length);
  }

  const keyMatch = rest.match(KEY_RE);
  if (keyMatch) {
    const key = keyMatch[1];
    tokens.push({ text: key, type: MODULE_NAME_RE.test(key) ? 'module' : 'key' });
    tokens.push({ text: ':', type: 'punctuation' });
    rest = rest.slice(key.length + 1);
  }

  if (rest === '') return tokens;

  const hashIndex = findCommentStart(rest);
  const valuePart = hashIndex === -1 ? rest : rest.slice(0, hashIndex);
  const commentPart = hashIndex === -1 ? '' : rest.slice(hashIndex);

  if (valuePart !== '') {
    const leadingSpaceMatch = valuePart.match(/^(\s+)/);
    const leadingSpace = leadingSpaceMatch ? leadingSpaceMatch[1] : '';
    if (leadingSpace) tokens.push({ text: leadingSpace, type: 'plain' });
    tokens.push(...tokenizeValue(valuePart.slice(leadingSpace.length)));
  }
  if (commentPart) tokens.push({ text: commentPart, type: 'comment' });

  return tokens;
}

function renderTokens(tokens: YamlToken[]) {
  return tokens.map((token, index) =>
    token.type === 'plain' ? (
      <span key={index}>{token.text}</span>
    ) : (
      <span key={index} className={`yaml-token-${token.type}`}>
        {token.text}
      </span>
    ),
  );
}

interface YamlHighlightProps {
  code: string;
  className?: string;
}

/** Lightweight, dependency-free YAML syntax highlighter for static playbook/doc examples. */
export function YamlHighlight({ code, className = '' }: YamlHighlightProps) {
  const lines = code.replace(/\n$/, '').split('\n');
  return (
    <pre className={`yaml-highlight ${className}`.trim()}>
      <code>
        {lines.map((line, index) => {
          const tokens = tokenizeLine(line);
          return (
            <div key={index} className="yaml-highlight-line">
              {tokens.length === 0 ? '\u00A0' : renderTokens(tokens)}
            </div>
          );
        })}
      </code>
    </pre>
  );
}
