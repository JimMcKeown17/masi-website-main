/**
 * Django Project Structure Parser
 * 
 * This script takes a tree command output and converts it into a structured knowledge 
 * base for Django projects, with intelligent categorization of components.
 */

function parseProjectStructure(treeOutput) {
  // Split the output into lines
  const lines = treeOutput.trim().split('\n');
  
  // Create the project structure object with Django-specific categorization
  const projectStructure = {
    name: "Masi Web Project",
    type: "Django Project",
    components: {
      apps: [],
      config: [],
      templates: [],
      static: [],
      scripts: []
    },
    structure: {
      name: lines[0] || "Project Root",
      type: "directory",
      children: []
    }
  };
  
  // Stack to keep track of the current path in the tree
  const stack = [projectStructure.structure];
  // Keep track of the current indentation level for each item in the stack
  const indentLevels = [0];
  
  // Process each line (skip the first line which is the root)
  for (let i = 1; i < lines.length; i++) {
    const line = lines[i];
    
    // Skip empty lines or the summary line at the end
    if (!line.trim() || line.includes('directories') || line.includes('files')) continue;
    
    // Determine the indentation level
    let indentLevel = 0;
    let j = 0;
    
    while (j < line.length && (line[j] === ' ' || line[j] === '│' || line[j] === '├' || line[j] === '└' || line[j] === '─')) {
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
      path: getCurrentPath(stack) + "/" + name
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
    
    // Categorize components based on Django project patterns
    categorizeComponent(projectStructure, newNode);
  }
  
  return projectStructure;
}

// Function to get the current path based on the stack
function getCurrentPath(stack) {
  return stack.map(node => node.name).join('/');
}

// Function to categorize components based on typical Django patterns
function categorizeComponent(projectStructure, node) {
  const path = node.path;
  const name = node.name;
  
  // Django apps (directories with models.py, views.py, etc.)
  if (node.type === "file" && 
      (name === "models.py" || name === "views.py" || name === "apps.py" || name === "urls.py") &&
      !path.includes("masi_website")) {
    
    // Extract app name from path
    const appName = path.split('/')[1]; // Assumes app is at top level directory
    
    // Check if app already in list
    if (!projectStructure.components.apps.some(app => app.name === appName)) {
      projectStructure.components.apps.push({
        name: appName,
        path: appName,
        files: []
      });
    }
    
    // Find app and add file
    const app = projectStructure.components.apps.find(app => app.name === appName);
    if (app && !app.files.includes(name)) {
      app.files.push(name);
    }
  }
  
  // Django settings and configuration
  if (node.type === "file" && 
      (name === "settings.py" || name === "urls.py" || name === "wsgi.py" || name === "asgi.py") &&
      path.includes("masi_website")) {
    
    projectStructure.components.config.push({
      name: name,
      path: path
    });
  }
  
  // Django templates
  if (path.includes("templates/") && node.type === "file" && name.endsWith(".html")) {
    projectStructure.components.templates.push({
      name: name,
      path: path
    });
  }
  
  // Static files
  if (path.includes("static/") && node.type === "file") {
    const category = path.split('/')[2] || "other"; // Get category from path (css, js, etc.)
    
    projectStructure.components.static.push({
      name: name,
      path: path,
      category: category
    });
  }
  
  // Python and shell scripts
  if (node.type === "file" && 
      (name.endsWith(".py") || name.endsWith(".sh")) && 
      !path.includes("/migrations/") &&
      !path.includes("/utils/") &&
      !path.includes("/management/") &&
      !path.includes("/services/") &&
      !path.includes("/visualizations/") &&
      !path.split('/')[1] || path.split('/')[1] === ".") {
    
    projectStructure.components.scripts.push({
      name: name,
      path: path
    });
  }
}

// Generate a markdown representation tailored for project knowledge
function generateProjectKnowledgeMarkdown(projectStructure) {
  let markdown = `# ${projectStructure.name}\n\n`;
  
  // Add app summaries
  markdown += `## Django Apps\n\n`;
  projectStructure.components.apps.forEach(app => {
    markdown += `### ${app.name}\n\n`;
    markdown += `Path: \`${app.path}\`\n\n`;
    markdown += "Files:\n";
    app.files.forEach(file => {
      markdown += `- ${file}\n`;
    });
    markdown += "\n";
  });
  
  // Add configuration files
  markdown += `## Configuration\n\n`;
  projectStructure.components.config.forEach(config => {
    markdown += `- \`${config.path}\`: ${getConfigDescription(config.name)}\n`;
  });
  markdown += "\n";
  
  // Add templates structure
  markdown += `## Templates\n\n`;
  const templatesByDirectory = groupByDirectory(projectStructure.components.templates);
  Object.keys(templatesByDirectory).sort().forEach(directory => {
    markdown += `### ${directory}\n\n`;
    templatesByDirectory[directory].forEach(template => {
      markdown += `- ${template.name}\n`;
    });
    markdown += "\n";
  });
  
  // Add static files summary
  markdown += `## Static Files\n\n`;
  const staticByCategory = groupByProperty(projectStructure.components.static, 'category');
  Object.keys(staticByCategory).sort().forEach(category => {
    markdown += `### ${category}\n\n`;
    if (staticByCategory[category].length > 20) {
      markdown += `*Contains ${staticByCategory[category].length} files*\n\n`;
      // For image folders, just provide a summary
      if (category === 'images') {
        markdown += "This directory contains various image assets including logos, banners, background images, and site content visuals.\n\n";
      } else if (category === 'js') {
        markdown += "Key JavaScript files:\n";
        staticByCategory[category].slice(0, 5).forEach(file => {
          markdown += `- ${file.name}\n`;
        });
        markdown += "\n";
      }
    } else {
      staticByCategory[category].forEach(file => {
        markdown += `- ${file.name}\n`;
      });
      markdown += "\n";
    }
  });
  
  // Add scripts summary
  markdown += `## Utility Scripts\n\n`;
  projectStructure.components.scripts.forEach(script => {
    markdown += `- \`${script.name}\`: ${getScriptDescription(script.name)}\n`;
  });
  
  return markdown;
}

// Group items by directory
function groupByDirectory(items) {
  const grouped = {};
  
  items.forEach(item => {
    const parts = item.path.split('/');
    // Get directory name, but handle special cases
    let dir = parts[parts.length - 2];
    
    if (!grouped[dir]) {
      grouped[dir] = [];
    }
    
    grouped[dir].push(item);
  });
  
  return grouped;
}

// Group items by a property
function groupByProperty(items, property) {
  const grouped = {};
  
  items.forEach(item => {
    const value = item[property];
    
    if (!grouped[value]) {
      grouped[value] = [];
    }
    
    grouped[value].push(item);
  });
  
  return grouped;
}

// Get description for configuration files
function getConfigDescription(filename) {
  const descriptions = {
    'settings.py': 'Django project settings including database configuration, middleware, and installed apps',
    'urls.py': 'URL routing configuration for the project',
    'wsgi.py': 'WSGI application entry point for web servers',
    'asgi.py': 'ASGI application entry point for asynchronous web servers'
  };
  
  return descriptions[filename] || filename;
}

// Get description for scripts
function getScriptDescription(filename) {
  // Add descriptions for known scripts
  const descriptions = {
    'manage.py': 'Django command-line utility for executing management commands',
    'build.sh': 'Build script for the project',
    'requirements.txt': 'Python dependencies for the project',
    'generate-fake-data.py': 'Script to generate test data',
    'delete-fake-data.py': 'Script to clean up test data'
  };
  
  return descriptions[filename] || 'Utility script';
}

// Generate a comprehensive project insight as JSON
function generateProjectInsights(projectStructure) {
  const insights = {
    projectType: "Django Web Application",
    projectName: "Masi Web Project",
    summary: "A Django web application for the Masinyusane organization with dashboards, data visualizations, and public-facing pages.",
    apps: projectStructure.components.apps.map(app => ({
      name: app.name,
      purpose: getAppPurpose(app.name, app.files),
      hasModels: app.files.includes("models.py"),
      hasViews: app.files.includes("views.py"),
      hasUrls: app.files.includes("urls.py"),
      hasForms: app.files.includes("forms.py"),
      hasAdmin: app.files.includes("admin.py")
    })),
    frontendTech: detectFrontendTech(projectStructure),
    databaseTech: "SQLite (development)",
    staticFileHandling: "Managed through Django's staticfiles app",
    deploymentIndicators: detectDeploymentSetup(projectStructure),
    templateStructure: analyzeTemplateStructure(projectStructure)
  };
  
  return insights;
}

// Determine the purpose of an app based on its name and files
function getAppPurpose(appName, files) {
  switch(appName) {
    case "core":
      return "Core application providing base functionality and shared utilities";
    case "dashboards":
      return "Dashboard application for data visualization and analysis";
    case "pages":
      return "Public-facing website pages and content";
    case "masi_website":
      return "Main project configuration and settings";
    default:
      return `${appName} application`;
  }
}

// Detect frontend technologies used
function detectFrontendTech(projectStructure) {
  const tech = [];
  
  // Check for common frontend libraries in static files
  const jsFiles = projectStructure.components.static.filter(file => 
    file.path.includes('/js/') || file.name.endsWith('.js')
  ).map(file => file.name);
  
  if (jsFiles.some(file => file.includes('bootstrap'))) {
    tech.push("Bootstrap");
  }
  
  if (jsFiles.some(file => file.includes('plotly'))) {
    tech.push("Plotly.js (data visualization)");
  }
  
  if (jsFiles.some(file => file.includes('jquery'))) {
    tech.push("jQuery");
  }
  
  // Check for SCSS files
  const hasScss = projectStructure.components.static.some(file => 
    file.path.includes('/scss/') || file.name.endsWith('.scss')
  );
  
  if (hasScss) {
    tech.push("SCSS (Sass CSS preprocessor)");
  }
  
  return tech;
}

// Detect deployment setup
function detectDeploymentSetup(projectStructure) {
  const indicators = [];
  
  // Check for common deployment files
  const rootFiles = projectStructure.structure.children.filter(node => node.type === "file").map(node => node.name);
  
  if (rootFiles.includes('build.sh')) {
    indicators.push("Custom build script");
  }
  
  if (rootFiles.includes('moonlit-botany-454016-b5-e20993bb54e0.json')) {
    indicators.push("Google Cloud service account credentials");
  }
  
  if (rootFiles.includes('requirements.txt')) {
    indicators.push("Python dependencies for deployment");
  }
  
  return indicators;
}

// Analyze template structure
function analyzeTemplateStructure(projectStructure) {
  const templates = projectStructure.components.templates;
  const templateFolders = {};
  
  templates.forEach(template => {
    const path = template.path;
    const folder = path.split('/').slice(0, -1).pop();
    
    if (!templateFolders[folder]) {
      templateFolders[folder] = 0;
    }
    
    templateFolders[folder]++;
  });
  
  // Check for base template
  const hasBaseTemplate = templates.some(template => template.name === "base.html");
  
  return {
    hasBaseTemplate,
    templateFolders
  };
}

// Function to process tree output and generate all formats
function processTreeOutput(treeOutput) {
  console.log("Processing Django project tree...");
  
  try {
    // Parse the tree output with Django-specific logic
    const projectStructure = parseProjectStructure(treeOutput);
    
    // Generate the markdown knowledge base
    const markdown = generateProjectKnowledgeMarkdown(projectStructure);
    
    // Generate the JSON insights
    const insights = generateProjectInsights(projectStructure);
    
    return {
      projectStructure,
      markdown,
      insights
    };
  } catch (error) {
    console.error("Error processing tree output:", error);
    return null;
  }
}

// Example usage:
// const treeOutput = fs.readFileSync('tree-output.txt', 'utf8');
// const result = processTreeOutput(treeOutput);
// console.log(result.markdown);
// console.log(JSON.stringify(result.insights, null, 2));
