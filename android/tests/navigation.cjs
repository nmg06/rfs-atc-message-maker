// Follow the same responsive Tools menu as a person using a phone.
exports.go=async(page,screen)=>{
 const button=page.locator(`[data-screen="${screen}"]`);
 if(!await button.isVisible())await page.locator('#nav-more').click();
 await button.click();
 await page.waitForFunction(value=>window.screen===value || screen===value,screen);
};
