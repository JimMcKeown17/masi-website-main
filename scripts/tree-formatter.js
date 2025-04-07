/**
 * Tree Output Formatter
 * 
 * This script takes the output of a 'tree' command and converts it to 
 * structured JSON and markdown formats that can be used for project documentation.
 * 
 * Usage:
 * 1. Run the tree command: tree -L 3 -I 'venv|__pycache__|*.pyc|.git|node_modules' --dirsfirst
 * 2. Copy the output
 * 3. Paste the output as input to this script
 * 4. The script will generate formatted JSON and markdown representations
 */

// Sample usage:
// parseTreeOutput(treeOutput);

function parseTreeOutput(treeOutput) {
  // Split the output into lines
  const lines = treeOutput.trim().split('\n');
  
  // Initialize the project structure
  const projectStructure = {
    name: lines[0], // The first line typically contains the root directory name
    type: "directory",
    children: []
  };
  
  // Stack to keep track of the current path in the tree
  const stack = [projectStructure];
  // Keep track of the current indentation level for each item in the stack
  const indentLevels = [0];
  
  // Process each line (skip the first line which is the root)
  for (let i = 1; i < lines.length; i++) {
    const line = lines[i];
    
    // Skip empty lines
    if (!line.trim()) continue;
    
    // Determine the indentation level (count the number of spaces before the tree branch)
    let indentLevel = 0;
    let j = 0;
    
    while (j < line.length && (line[j] === ' ' || line[j] === '│' || line[j] === '├' || line[j] === '└' || line[j] === '─' || line[j] === '│' || line[j] === '│' || line[j] === '│' || line[j] === '│')) {
      j++;
      indentLevel++;
    }
    
    // Get the item name (remove the tree characters)
    const itemName = line.substring(j).trim();
    
    // Determine if this is a directory or a file
    const isDirectory = itemName.endsWith('/');
    const name = isDirectory ? itemName.substring(0, itemName.length - 1) : itemName;
    
    // Create the new node
    const newNode = {
      name: name,
      type: isDirectory ? "directory" : "file",
    };
    
    if (isDirectory) {
      newNode.children = [];
    }
    
    // Find the appropriate parent by comparing indentation levels
    while (indentLevels[indentLevels.length - 1] >= indentLevel) {
      stack.pop();
      indentLevels.pop();
    }
    
    // Add the new node to its parent
    stack[stack.length - 1].children.push(newNode);
    
    // If this is a directory, push it to the stack
    if (isDirectory) {
      stack.push(newNode);
      indentLevels.push(indentLevel);
    }
  }
  
  return projectStructure;
}

// Function to generate a markdown representation of the project structure
function generateMarkdown(node, indent = 0) {
  let result = '';
  
  // Add the current node
  if (indent > 0) {
    result += '  '.repeat(indent - 1) + '- ';
  }
  
  if (node.type === "directory") {
    result += `**${node.name}/**\n`;
    
    // Add children
    if (node.children) {
      for (const child of node.children) {
        result += generateMarkdown(child, indent + 1);
      }
    }
  } else {
    result += `${node.name}\n`;
  }
  
  return result;
}

// Function to convert the output to a flat structure for easier navigation
function generateFlatStructure(node, path = '') {
  let result = [];
  const currentPath = path ? `${path}/${node.name}` : node.name;
  
  if (node.type === "directory") {
    result.push({
      path: currentPath,
      type: "directory"
    });
    
    if (node.children) {
      for (const child of node.children) {
        result = result.concat(generateFlatStructure(child, currentPath));
      }
    }
  } else {
    result.push({
      path: currentPath,
      type: "file"
    });
  }
  
  return result;
}

// Main function to process tree output
function processTreeOutput(treeOutput) {
  console.log("Processing tree output...");
  
  try {
    // Parse the tree output
    const projectStructure = parseTreeOutput(treeOutput);
    
    // Generate the JSON output
    console.log("\n--- JSON Structure ---");
    console.log(JSON.stringify(projectStructure, null, 2));
    
    // Generate the markdown output
    console.log("\n--- Markdown Structure ---");
    console.log(generateMarkdown(projectStructure));
    
    // Generate the flat structure
    console.log("\n--- Flat Structure ---");
    console.log(JSON.stringify(generateFlatStructure(projectStructure), null, 2));
    
    return {
      json: projectStructure,
      markdown: generateMarkdown(projectStructure),
      flat: generateFlatStructure(projectStructure)
    };
  } catch (error) {
    console.error("Error processing tree output:", error);
    return null;
  }
}

// Example usage:
// Paste your tree output below and uncomment these lines to test
/*
const treeOutput = `your_project_root
├── src/
│   ├── components/
│   │   ├── Button.js
│   │   └── Form.js
│   └── utils/
│       └── helpers.js
└── package.json`;

processTreeOutput(treeOutput);
*/
