"use strict";
document.querySelectorAll('[data-confirm]').forEach(form=>form.addEventListener('submit',e=>{if(!confirm(form.dataset.confirm))e.preventDefault()}));
document.querySelectorAll('.attachment-input').forEach(input=>{
 const form=input.closest('form'),drop=form.querySelector('.upload-drop'),preview=form.querySelector('.previews');
 const show=()=>{preview.replaceChildren();for(const file of input.files){const box=document.createElement('div');box.className='preview';if(file.type.startsWith('image/')){const img=document.createElement('img');const url=URL.createObjectURL(file);img.src=url;img.onload=()=>URL.revokeObjectURL(url);box.append(img)}const caption=document.createElement('div');caption.textContent=file.name;box.append(caption);preview.append(box)}};
 const add=files=>{const dt=new DataTransfer();for(const f of input.files)dt.items.add(f);for(const f of files)dt.items.add(f);if(dt.files.length>5){alert('每次最多5個附件');return}input.files=dt.files;show()};
 input.addEventListener('change',show);
 if(drop){drop.addEventListener('dragover',e=>{e.preventDefault();drop.classList.add('drag')});drop.addEventListener('dragleave',()=>drop.classList.remove('drag'));drop.addEventListener('drop',e=>{e.preventDefault();drop.classList.remove('drag');add(e.dataTransfer.files)})}
 form.addEventListener('paste',e=>{const files=Array.from(e.clipboardData.items).filter(x=>x.kind==='file').map(x=>x.getAsFile());if(files.length){e.preventDefault();add(files)}});
});
const ticketForm=document.querySelector('#ticket-form');
if(ticketForm){
 const notice=document.querySelector('#version-notice');
 let latest=Number(ticketForm.dataset.version);
 async function checkVersion(){try{const response=await fetch(ticketForm.dataset.statusUrl+'?version='+ticketForm.dataset.version,{cache:'no-store'});if(!response.ok)return;const state=await response.json();latest=state.latest;if(String(state.latest)!==ticketForm.dataset.version){notice.hidden=false;notice.textContent=state.accepted?'表單已有新版，目前版本仍可送出；可保留文字並切換新版。':'此版本已停止接受，請保留文字並切換新版；附件需要重新選取。'}}catch(e){/* Submission always revalidates server-side. */}}
 setInterval(checkVersion,20000);document.addEventListener('visibilitychange',()=>{if(!document.hidden)checkVersion()});checkVersion();
 ticketForm.addEventListener('submit',e=>{if(e.submitter?.name==='switch_version' && ticketForm.querySelector('.attachment-input').files.length && !confirm('切換新版會保留文字，但附件需要重新選取。是否繼續？'))e.preventDefault()});
}

const designer=document.querySelector('#form-designer');
if(designer){
 const hidden=designer.querySelector('[name=fields]'),container=document.querySelector('#field-builder');
 let fields=[];try{fields=JSON.parse(hidden.value||'[]')}catch(e){}
 const save=()=>{hidden.value=JSON.stringify(fields)};
 function draw(){container.replaceChildren();fields.forEach((field,index)=>{
  const box=document.createElement('div');box.className='field-editor';
  function input(label,key,type='text'){
   const wrapper=document.createElement('label');wrapper.textContent=label;const el=document.createElement('input');el.type=type;
   if(type==='checkbox')el.checked=Boolean(field[key]);else{el.value=field[key]||'';el.required=true}
   if(key==='key'){el.pattern='[a-z][a-z0-9_]{0,39}';el.title='使用小寫英文字母開頭，搭配數字及底線'}
   el.addEventListener('input',()=>{field[key]=type==='checkbox'?el.checked:el.value;save()});wrapper.append(el);box.append(wrapper)
  }
  input('欄位名稱','label');input('欄位代碼（同一欄位請沿用）','key');
  const label=document.createElement('label');label.textContent='輸入方式';const select=document.createElement('select');
  for(const [value,text] of [['text','單行文字'],['textarea','多行文字'],['number','數字'],['date','日期'],['select','下拉選單']]){const option=document.createElement('option');option.value=value;option.textContent=text;select.append(option)}
  select.value=field.type;label.append(select);box.append(label);
  select.addEventListener('change',()=>{field.type=select.value;if(field.type==='select'&&!field.options)field.options=['選項一'];save();draw()});
  input('必填','required','checkbox');
  if(field.type==='select'){const l=document.createElement('label');l.textContent='選項（每行一筆）';const t=document.createElement('textarea');t.value=(field.options||[]).join('\n');t.required=true;t.addEventListener('input',()=>{field.options=t.value.split('\n').map(x=>x.trim()).filter(Boolean);save()});l.append(t);box.append(l)}
  const remove=document.createElement('button');remove.type='button';remove.className='danger';remove.textContent='移除此欄位';remove.addEventListener('click',()=>{fields.splice(index,1);save();draw()});box.append(remove);container.append(box)
 });save()}
 document.querySelector('#add-field').addEventListener('click',()=>{if(fields.length>=40){alert('最多40個欄位');return}fields.push({key:'field_'+Date.now(),label:'',type:'text',required:false});draw()});draw();
}
