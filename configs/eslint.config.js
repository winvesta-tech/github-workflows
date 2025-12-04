// ESLint configuration for JavaScript/TypeScript code quality
// Requires: eslint @typescript-eslint/parser @typescript-eslint/eslint-plugin eslint-plugin-sonarjs

module.exports = {
  root: true,
  parser: '@typescript-eslint/parser',
  parserOptions: {
    ecmaVersion: 2022,
    sourceType: 'module',
    ecmaFeatures: {
      jsx: true,
    },
  },
  env: {
    browser: true,
    node: true,
    es2022: true,
    jest: true,
  },
  plugins: [
    '@typescript-eslint',
    'sonarjs',
  ],
  extends: [
    'eslint:recommended',
    'plugin:sonarjs/recommended',
  ],
  rules: {
    // Complexity rules (these affect quality score)
    'complexity': ['warn', { max: 10 }],
    'max-depth': ['warn', { max: 4 }],
    'max-nested-callbacks': ['warn', { max: 3 }],
    'max-lines-per-function': ['warn', { max: 50, skipBlankLines: true, skipComments: true }],
    
    // Code smell rules
    'no-duplicate-imports': 'error',
    'no-unused-vars': 'warn',
    'no-console': 'warn',
    'no-debugger': 'error',
    'no-alert': 'warn',
    'no-empty': 'warn',
    'no-extra-semi': 'error',
    'no-unreachable': 'error',
    'no-constant-condition': 'warn',
    
    // SonarJS rules for cognitive complexity and code smells
    'sonarjs/cognitive-complexity': ['warn', 15],
    'sonarjs/no-duplicate-string': ['warn', { threshold: 3 }],
    'sonarjs/no-identical-functions': 'warn',
    'sonarjs/no-collapsible-if': 'warn',
    'sonarjs/no-redundant-jump': 'warn',
    'sonarjs/prefer-immediate-return': 'warn',
    'sonarjs/no-nested-switch': 'warn',
    'sonarjs/no-nested-template-literals': 'warn',
    
    // Best practices
    'eqeqeq': ['error', 'always'],
    'curly': ['error', 'all'],
    'default-case': 'warn',
    'no-eval': 'error',
    'no-implied-eval': 'error',
    'no-new-func': 'error',
    'no-return-await': 'warn',
    'prefer-const': 'warn',
    'prefer-template': 'warn',
  },
  overrides: [
    {
      // TypeScript specific rules
      files: ['*.ts', '*.tsx'],
      rules: {
        '@typescript-eslint/no-unused-vars': 'warn',
        '@typescript-eslint/no-explicit-any': 'warn',
        '@typescript-eslint/explicit-function-return-type': 'off',
        '@typescript-eslint/no-non-null-assertion': 'warn',
      },
    },
    {
      // Test files - relaxed rules
      files: ['*.test.js', '*.test.ts', '*.spec.js', '*.spec.ts', '**/__tests__/**'],
      rules: {
        'max-lines-per-function': 'off',
        'sonarjs/no-duplicate-string': 'off',
      },
    },
  ],
  ignorePatterns: [
    'node_modules/',
    'dist/',
    'build/',
    'coverage/',
    '*.min.js',
  ],
};
