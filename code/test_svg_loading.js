const puppeteer = require('puppeteer');

(async () => {
  try {
    // Launch browser
    const browser = await puppeteer.launch({ headless: false });
    const page = await browser.newPage();
    page.setDefaultTimeout(60000);
    
    // Enable console logging
    page.on('console', (msg) => console.log('Browser console:', msg.text()));
    page.on('pageerror', (err) => console.error('Page error:', err));
    
    // Navigate to the mock climber page
    await page.goto('http://localhost:8000/walls/264d7633-65b2-41a8-92a4-34eb79a891bb/mock-climber/');
    
    // Wait for page to load
    await page.waitForSelector('#wallImage', { visible: true });
    console.log('Page loaded');
    
    // Wait for SVG to load
    await page.waitForTimeout(2000);
    
    // Check if SVG container is visible
    const svgVisible = await page.evaluate(() => {
      const container = document.getElementById('wallSvgContainer');
      if (!container) return 'No container';
      
      return window.getComputedStyle(container).opacity;
    });
    
    console.log('SVG opacity:', svgVisible);
    
    // Check if SVG has content
    const svgContent = await page.evaluate(() => {
      const container = document.getElementById('wallSvgContainer');
      if (!container) return 'No container';
      
      return container.innerHTML;
    });
    
    console.log('SVG content length:', svgContent.length);
    
    // Take screenshot
    await page.screenshot({ path: 'mock_climber_test.png', fullPage: true });
    console.log('Screenshot saved');
    
    // Close browser
    await browser.close();
  } catch (error) {
    console.error('Test failed:', error);
  }
})();