const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require(process.env.SJAGENT_PLAYWRIGHT_PATH || 'playwright');
const url = 'http://127.0.0.1:5179';
const root = path.resolve(__dirname, '..');

async function pixels(page) {
  return page.locator('.product-model-preview-dialog canvas').evaluate(async (canvas) => {
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const c = document.createElement('canvas'); c.width = canvas.width; c.height = canvas.height;
    const ctx = c.getContext('2d'); ctx.drawImage(canvas, 0, 0);
    const p = ctx.getImageData(0, 0, c.width, c.height).data;
    let hash = 2166136261, blue = 0, red = 0, minX=c.width,minY=c.height,maxX=0,maxY=0;
    for (let y=0;y<c.height;y+=3) for(let x=0;x<c.width;x+=3) {
      const i=(y*c.width+x)*4;
      for(let n=0;n<3;n++)hash=Math.imul(hash^p[i+n],16777619);
      if(p[i]>50&&p[i]>p[i+1]*1.2&&p[i]>p[i+2]*1.2)red++;
      if(p[i+2]>50&&p[i+2]>p[i]*1.2&&p[i+2]>p[i+1]*1.1){blue++;minX=Math.min(minX,x);maxX=Math.max(maxX,x);minY=Math.min(minY,y);maxY=Math.max(maxY,y);}
    }
    return {hash,blue,red,minX,minY,maxX,maxY,width:c.width,height:c.height};
  });
}
async function ready(page) {
  await page.waitForFunction(()=>['ready','error'].includes(document.querySelector('.product-model-preview-stage')?.dataset.state));
  assert.equal(await page.locator('.product-model-preview-stage').getAttribute('data-state'),'ready',await page.locator('.product-model-preview-stage').innerText());
}
async function editor(page) {
  await page.locator('.product-spu-card').filter({hasText:'【模型测试】三小盒'}).first().getByRole('button',{name:'编辑',exact:true}).click();
  await page.getByRole('tab',{name:'3D 模型',exact:true}).click();
  await page.getByRole('combobox',{name:'换色材质',exact:true}).waitFor();
  await page.waitForFunction(()=>!document.querySelector('.product-editor-dialog button:last-child')?.disabled);
}
async function preview(page) {
  await page.getByRole('button',{name:'预览',exact:true}).click();await ready(page);
  assert.equal(await page.locator('.product-model-preview-canvas').getAttribute('data-pose'),'open');
}

(async()=>{
  await fs.mkdir(path.join(root,'.tmp'),{recursive:true});
  const browser=await chromium.launch({headless:true,executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,
    args:['--enable-webgl','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
  const errors=[],requests=[];let page;
  try {
    const context=await browser.newContext({viewport:{width:1440,height:1000}});
    const login=await context.request.post(url+'/api/web-auth/login',{data:{username:'model_demo',password:'ModelPreview123!'}});
    assert.equal((await login.json()).code,0);
    const me=(await(await context.request.get(url+'/api/web-auth/me')).json()).data.user;
    assert.equal(me.username,'model_demo','never edit business products');
    page=await context.newPage();page.setDefaultTimeout(90000);
    page.on('pageerror',e=>errors.push(e.message));
    page.on('request',r=>{if(/\.glb(?:\?|$)/.test(r.url()))requests.push(r.url());});
    await page.goto(url+'/admin/products');await editor(page);
    assert.equal(requests.length,0,'no eager GLB download');
    await page.getByRole('combobox',{name:'换色材质',exact:true}).click();
    await page.getByRole('option',{name:/^材质 · #\d+$/}).click();
    await page.getByRole('textbox',{name:/红色 HEX/}).fill('#B61528');
    await page.getByRole('textbox',{name:/蓝色 HEX/}).fill('#2B67C8');
    await page.getByRole('combobox',{name:'默认颜色',exact:true}).click();
    await page.getByRole('option',{name:'蓝色',exact:true}).click();
    await page.getByRole('textbox',{name:/红色 HEX/}).fill('#BAD');
    assert.equal(await page.getByRole('button',{name:'保存商品',exact:true}).isEnabled(),false,'partial HEX blocks save');
    await page.getByRole('textbox',{name:/红色 HEX/}).fill('#B61528');
    await preview(page);
    const blue=await pixels(page);assert.ok(blue.blue>1000,'actual model is blue');
    const downloads=requests.length;
    await page.getByRole('button',{name:'红色',exact:true}).click();
    const red=await pixels(page);assert.ok(red.red>1000&&red.blue<blue.blue/2,'actual shell switches to red');
    assert.equal(requests.length,downloads,'colors do not refetch GLB');
    await page.getByRole('button',{name:'合上礼盒',exact:true}).click();
    await page.waitForFunction(()=>document.querySelector('.product-model-preview-canvas')?.dataset.pose==='closed');
    await page.getByRole('button',{name:'蓝色',exact:true}).click();
    assert.equal(await page.locator('.product-model-preview-canvas').getAttribute('data-pose'),'closed','color preserves pose');
    const canvas=await page.locator('.product-model-preview-dialog canvas').boundingBox();
    await page.mouse.move(canvas.x+canvas.width/2,canvas.y+canvas.height/2);await page.mouse.down();
    await page.mouse.move(canvas.x+canvas.width/2+210,canvas.y+canvas.height/2+35,{steps:15});await page.mouse.up();
    await page.waitForTimeout(600);
    await page.getByRole('button',{name:'设为默认正面',exact:true}).click();
    await page.locator('.product-model-preview-dialog .sj-dialog-close').click();
    const save=page.waitForResponse(r=>r.url().endsWith('/api/product/save')&&r.request().method()==='POST');
    await page.getByRole('button',{name:'保存商品',exact:true}).click();
    const saved=await(await save).json();assert.equal(saved.code,0,JSON.stringify(saved));
    const id=saved.data.id;
    const detail=(await(await context.request.get(url+'/api/product/'+id)).json()).data;
    assert.equal(Object.values(detail.model_config.sku_colors).length,2);
    assert.ok(detail.model_config.camera_direction?.length===3);
    assert.equal(detail.model_config.default_pose,'open');
    const mini=(await(await context.request.get(url+'/api/mini/goods/detail?id='+id)).json()).data;
    assert.ok(JSON.stringify(mini).includes('#2B67C8'),'mini data contains saved colors');
    assert.ok(!JSON.stringify(mini).includes('oss_key'),'mini never leaks storage management fields');
    await editor(page);await preview(page);
    assert.ok((await pixels(page)).blue>1000,'saved default color returns');
    await page.screenshot({path:path.join(root,'.tmp/model-config-desktop.png')});
    await page.getByRole('button',{name:'恢复默认正面',exact:true}).click();
    await page.locator('.product-model-preview-dialog .sj-dialog-close').click();
    await page.getByRole('button',{name:'取消',exact:true}).click();
    const afterCancel=(await(await context.request.get(url+'/api/product/'+id)).json()).data;
    assert.deepEqual(afterCancel.model_config.camera_direction,detail.model_config.camera_direction,'cancel preserves saved calibration');
    await page.setViewportSize({width:390,height:844});await editor(page);
    await page.screenshot({path:path.join(root,'.tmp/model-config-editor-mobile.png')});
    await preview(page);const mobile=await pixels(page);
    assert.ok(mobile.blue>300&&mobile.minX>0&&mobile.maxX<mobile.width-1&&mobile.minY>0&&mobile.maxY<mobile.height-1,'mobile model visible and contained');
    await page.screenshot({path:path.join(root,'.tmp/model-config-mobile.png')});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    for (const width of [1280,1920,2560]) {
      await page.setViewportSize({width,height:width===2560?1440:1000});
      const bounds=await pixels(page);
      assert.ok(bounds.blue>1000&&bounds.minX>0&&bounds.maxX<bounds.width-1&&bounds.minY>0&&bounds.maxY<bounds.height-1,`model fits ${width}px`);
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    }
    await page.locator('.product-model-preview-dialog .sj-dialog-close').click();
    await page.getByRole('button',{name:'取消',exact:true}).click();
    assert.deepEqual(errors,[]);
    console.log(JSON.stringify({productId:id,blue,red,mobile,checks:['SKU-colors','GLB-material-index','open-default','color-preserves-pose','no-refetch','calibrate-save','cancel-calibration','mini-contract','mobile'],errors},null,2));
  }catch(error){if(page)await page.screenshot({path:path.join(root,'.tmp/model-config-browser-failure.png')}).catch(()=>{});throw error;}
  finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
