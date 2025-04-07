/**
 * Simple Tree Formatter (Debug Version)
 * 
 * This script reads tree command output from a file and generates 
 * structured project documentation with clear path output.
 * 
 * Save this as simple-tree.js and run:
 * node simple-tree.js
 */

const fs = require('fs');
const path = require('path');

// Check if tree-output.txt exists, if not, create a sample
if (!fs.existsSync('tree-output.txt')) {
  console.log('tree-output.txt not found, creating a sample file...');
  const sampleOutput = `sample_project
├── src/
│   ├── components/
│   │   ├── Button.js
│   │   └── Form.js
│   └── utils/
│       └── helpers.js
└── package.json`;
  
  fs.writeFileSync('tree-output.txt', sampleOutput);
  console.log('Sample tree-output.txt created.');
}

// Read the tree output
console.log('Reading tree output...');
const treeOutput = fs.readFileSync('tree-output.txt', 'utf8');
console.log('Tree output loaded, length:', treeOutput.length, 'characters');

// Generate a simple markdown structure
console.log('Generating markdown...');
const lines = treeOutput.split('\n');
let markdown = '# Project Structure\n\n';

for (const line of lines) {
  markdown += line + '\n';
}

// Get the current working directory for logging
const currentDir = process.cwd();
console.log('Current working directory:', currentDir);

// File paths for output
const jsonPath = path.join(currentDir, 'project-structure.json');
const mdPath = path.join(currentDir, 'project-structure.md');

// Write the output files
console.log('Writing output files...');
try {
  // Write a simple JSON representation
  fs.writeFileSync(jsonPath, JSON.stringify({ 
    output: treeOutput,
    lines: lines.length
  }, null, 2));
  console.log('JSON file written to:', jsonPath);
  
  // Write the markdown
  fs.writeFileSync(mdPath, markdown);
  console.log('Markdown file written to:', mdPath);
  
  console.log('All files written successfully!');
} catch (error) {
  console.error('Error writing files:', error);
}
