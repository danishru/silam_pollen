/**
@license
Copyright (c) 2019 The Polymer Project Authors. All rights reserved.
This code may only be used under the BSD style license found at
http://polymer.github.io/LICENSE.txt The complete set of authors may be found at
http://polymer.github.io/AUTHORS.txt The complete set of contributors may be
found at http://polymer.github.io/CONTRIBUTORS.txt Code distributed by Google as
part of the polymer project is also subject to an additional IP rights grant
found at http://polymer.github.io/PATENTS.txt
*/

const isCEPolyfill=typeof window!=="undefined"&&window.customElements!=null&&window.customElements.polyfillWrapFlushCallback!==undefined;const removeNodes=(container,start,end=null)=>{while(start!==end){const n=start.nextSibling;container.removeChild(start);start=n}};const marker=`{{lit-${String(Math.random()).slice(2)}}}`;const nodeMarker=`\x3c!--${marker}--\x3e`;const markerRegex=new RegExp(`${marker}|${nodeMarker}`);const boundAttributeSuffix="$lit$";class Template{constructor(result,element){this.parts=[];this.element=element;const nodesToRemove=[];const stack=[];const walker=document.createTreeWalker(element.content,133,null,false);let lastPartIndex=0;let index=-1;let partIndex=0;const{strings:strings,values:{length:length}}=result;while(partIndex<length){const node=walker.nextNode();if(node===null){walker.currentNode=stack.pop();continue}index++;if(node.nodeType===1){if(node.hasAttributes()){const attributes=node.attributes;const{length:length}=attributes;let count=0;for(let i=0;i<length;i++){if(endsWith(attributes[i].name,boundAttributeSuffix)){count++}}while(count-- >0){const stringForPart=strings[partIndex];const name=lastAttributeNameRegex.exec(stringForPart)[2];const attributeLookupName=name.toLowerCase()+boundAttributeSuffix;const attributeValue=node.getAttribute(attributeLookupName);node.removeAttribute(attributeLookupName);const statics=attributeValue.split(markerRegex);this.parts.push({type:"attribute",index:index,name:name,strings:statics});partIndex+=statics.length-1}}if(node.tagName==="TEMPLATE"){stack.push(node);walker.currentNode=node.content}}else if(node.nodeType===3){const data=node.data;if(data.indexOf(marker)>=0){const parent=node.parentNode;const strings=data.split(markerRegex);const lastIndex=strings.length-1;for(let i=0;i<lastIndex;i++){let insert;let s=strings[i];if(s===""){insert=createMarker()}else{const match=lastAttributeNameRegex.exec(s);if(match!==null&&endsWith(match[2],boundAttributeSuffix)){s=s.slice(0,match.index)+match[1]+match[2].slice(0,-boundAttributeSuffix.length)+match[3]}insert=document.createTextNode(s)}parent.insertBefore(insert,node);this.parts.push({type:"node",index:++index})}if(strings[lastIndex]===""){parent.insertBefore(createMarker(),node);nodesToRemove.push(node)}else{node.data=strings[lastIndex]}partIndex+=lastIndex}}else if(node.nodeType===8){if(node.data===marker){const parent=node.parentNode;if(node.previousSibling===null||index===lastPartIndex){index++;parent.insertBefore(createMarker(),node)}lastPartIndex=index;this.parts.push({type:"node",index:index});if(node.nextSibling===null){node.data=""}else{nodesToRemove.push(node);index--}partIndex++}else{let i=-1;while((i=node.data.indexOf(marker,i+1))!==-1){this.parts.push({type:"node",index:-1});partIndex++}}}}for(const n of nodesToRemove){n.parentNode.removeChild(n)}}}const endsWith=(str,suffix)=>{const index=str.length-suffix.length;return index>=0&&str.slice(index)===suffix};const isTemplatePartActive=part=>part.index!==-1;const createMarker=()=>document.createComment("");const lastAttributeNameRegex=/([ \x09\x0a\x0c\x0d])([^\0-\x1F\x7F-\x9F "'>=/]+)([ \x09\x0a\x0c\x0d]*=[ \x09\x0a\x0c\x0d]*(?:[^ \x09\x0a\x0c\x0d"'`<>=]*|"[^"]*|'[^']*))$/;const walkerNodeFilter=133;function removeNodesFromTemplate(template,nodesToRemove){const{element:{content:content},parts:parts}=template;const walker=document.createTreeWalker(content,walkerNodeFilter,null,false);let partIndex=nextActiveIndexInTemplateParts(parts);let part=parts[partIndex];let nodeIndex=-1;let removeCount=0;const nodesToRemoveInTemplate=[];let currentRemovingNode=null;while(walker.nextNode()){nodeIndex++;const node=walker.currentNode;if(node.previousSibling===currentRemovingNode){currentRemovingNode=null}if(nodesToRemove.has(node)){nodesToRemoveInTemplate.push(node);if(currentRemovingNode===null){currentRemovingNode=node}}if(currentRemovingNode!==null){removeCount++}while(part!==undefined&&part.index===nodeIndex){part.index=currentRemovingNode!==null?-1:part.index-removeCount;partIndex=nextActiveIndexInTemplateParts(parts,partIndex);part=parts[partIndex]}}nodesToRemoveInTemplate.forEach((n=>n.parentNode.removeChild(n)))}const countNodes=node=>{let count=node.nodeType===11?0:1;const walker=document.createTreeWalker(node,walkerNodeFilter,null,false);while(walker.nextNode()){count++}return count};const nextActiveIndexInTemplateParts=(parts,startIndex=-1)=>{for(let i=startIndex+1;i<parts.length;i++){const part=parts[i];if(isTemplatePartActive(part)){return i}}return-1};function insertNodeIntoTemplate(template,node,refNode=null){const{element:{content:content},parts:parts}=template;if(refNode===null||refNode===undefined){content.appendChild(node);return}const walker=document.createTreeWalker(content,walkerNodeFilter,null,false);let partIndex=nextActiveIndexInTemplateParts(parts);let insertCount=0;let walkerIndex=-1;while(walker.nextNode()){walkerIndex++;const walkerNode=walker.currentNode;if(walkerNode===refNode){insertCount=countNodes(node);refNode.parentNode.insertBefore(node,refNode)}while(partIndex!==-1&&parts[partIndex].index===walkerIndex){if(insertCount>0){while(partIndex!==-1){parts[partIndex].index+=insertCount;partIndex=nextActiveIndexInTemplateParts(parts,partIndex)}return}partIndex=nextActiveIndexInTemplateParts(parts,partIndex)}}}const directives=new WeakMap;const isDirective=o=>typeof o==="function"&&directives.has(o);const noChange={};const nothing={};class TemplateInstance{constructor(template,processor,options){this.__parts=[];this.template=template;this.processor=processor;this.options=options}update(values){let i=0;for(const part of this.__parts){if(part!==undefined){part.setValue(values[i])}i++}for(const part of this.__parts){if(part!==undefined){part.commit()}}}_clone(){const fragment=isCEPolyfill?this.template.element.content.cloneNode(true):document.importNode(this.template.element.content,true);const stack=[];const parts=this.template.parts;const walker=document.createTreeWalker(fragment,133,null,false);let partIndex=0;let nodeIndex=0;let part;let node=walker.nextNode();while(partIndex<parts.length){part=parts[partIndex];if(!isTemplatePartActive(part)){this.__parts.push(undefined);partIndex++;continue}while(nodeIndex<part.index){nodeIndex++;if(node.nodeName==="TEMPLATE"){stack.push(node);walker.currentNode=node.content}if((node=walker.nextNode())===null){walker.currentNode=stack.pop();node=walker.nextNode()}}if(part.type==="node"){const part=this.processor.handleTextExpression(this.options);part.insertAfterNode(node.previousSibling);this.__parts.push(part)}else{this.__parts.push(...this.processor.handleAttributeExpressions(node,part.name,part.strings,this.options))}partIndex++}if(isCEPolyfill){document.adoptNode(fragment);customElements.upgrade(fragment)}return fragment}}const policy=window.trustedTypes&&trustedTypes.createPolicy("lit-html",{createHTML:s=>s});const commentMarker=` ${marker} `;class TemplateResult{constructor(strings,values,type,processor){this.strings=strings;this.values=values;this.type=type;this.processor=processor}getHTML(){const l=this.strings.length-1;let html="";let isCommentBinding=false;for(let i=0;i<l;i++){const s=this.strings[i];const commentOpen=s.lastIndexOf("\x3c!--");isCommentBinding=(commentOpen>-1||isCommentBinding)&&s.indexOf("--\x3e",commentOpen+1)===-1;const attributeMatch=lastAttributeNameRegex.exec(s);if(attributeMatch===null){html+=s+(isCommentBinding?commentMarker:nodeMarker)}else{html+=s.substr(0,attributeMatch.index)+attributeMatch[1]+attributeMatch[2]+boundAttributeSuffix+attributeMatch[3]+marker}}html+=this.strings[l];return html}getTemplateElement(){const template=document.createElement("template");let value=this.getHTML();if(policy!==undefined){value=policy.createHTML(value)}template.innerHTML=value;return template}}const isPrimitive=value=>value===null||!(typeof value==="object"||typeof value==="function");const isIterable=value=>Array.isArray(value)||!!(value&&value[Symbol.iterator]);class AttributeCommitter{constructor(element,name,strings){this.dirty=true;this.element=element;this.name=name;this.strings=strings;this.parts=[];for(let i=0;i<strings.length-1;i++){this.parts[i]=this._createPart()}}_createPart(){return new AttributePart(this)}_getValue(){const strings=this.strings;const l=strings.length-1;const parts=this.parts;if(l===1&&strings[0]===""&&strings[1]===""){const v=parts[0].value;if(typeof v==="symbol"){return String(v)}if(typeof v==="string"||!isIterable(v)){return v}}let text="";for(let i=0;i<l;i++){text+=strings[i];const part=parts[i];if(part!==undefined){const v=part.value;if(isPrimitive(v)||!isIterable(v)){text+=typeof v==="string"?v:String(v)}else{for(const t of v){text+=typeof t==="string"?t:String(t)}}}}text+=strings[l];return text}commit(){if(this.dirty){this.dirty=false;this.element.setAttribute(this.name,this._getValue())}}}class AttributePart{constructor(committer){this.value=undefined;this.committer=committer}setValue(value){if(value!==noChange&&(!isPrimitive(value)||value!==this.value)){this.value=value;if(!isDirective(value)){this.committer.dirty=true}}}commit(){while(isDirective(this.value)){const directive=this.value;this.value=noChange;directive(this)}if(this.value===noChange){return}this.committer.commit()}}class NodePart{constructor(options){this.value=undefined;this.__pendingValue=undefined;this.options=options}appendInto(container){this.startNode=container.appendChild(createMarker());this.endNode=container.appendChild(createMarker())}insertAfterNode(ref){this.startNode=ref;this.endNode=ref.nextSibling}appendIntoPart(part){part.__insert(this.startNode=createMarker());part.__insert(this.endNode=createMarker())}insertAfterPart(ref){ref.__insert(this.startNode=createMarker());this.endNode=ref.endNode;ref.endNode=this.startNode}setValue(value){this.__pendingValue=value}commit(){if(this.startNode.parentNode===null){return}while(isDirective(this.__pendingValue)){const directive=this.__pendingValue;this.__pendingValue=noChange;directive(this)}const value=this.__pendingValue;if(value===noChange){return}if(isPrimitive(value)){if(value!==this.value){this.__commitText(value)}}else if(value instanceof TemplateResult){this.__commitTemplateResult(value)}else if(value instanceof Node){this.__commitNode(value)}else if(isIterable(value)){this.__commitIterable(value)}else if(value===nothing){this.value=nothing;this.clear()}else{this.__commitText(value)}}__insert(node){this.endNode.parentNode.insertBefore(node,this.endNode)}__commitNode(value){if(this.value===value){return}this.clear();this.__insert(value);this.value=value}__commitText(value){const node=this.startNode.nextSibling;value=value==null?"":value;const valueAsString=typeof value==="string"?value:String(value);if(node===this.endNode.previousSibling&&node.nodeType===3){node.data=valueAsString}else{this.__commitNode(document.createTextNode(valueAsString))}this.value=value}__commitTemplateResult(value){const template=this.options.templateFactory(value);if(this.value instanceof TemplateInstance&&this.value.template===template){this.value.update(value.values)}else{const instance=new TemplateInstance(template,value.processor,this.options);const fragment=instance._clone();instance.update(value.values);this.__commitNode(fragment);this.value=instance}}__commitIterable(value){if(!Array.isArray(this.value)){this.value=[];this.clear()}const itemParts=this.value;let partIndex=0;let itemPart;for(const item of value){itemPart=itemParts[partIndex];if(itemPart===undefined){itemPart=new NodePart(this.options);itemParts.push(itemPart);if(partIndex===0){itemPart.appendIntoPart(this)}else{itemPart.insertAfterPart(itemParts[partIndex-1])}}itemPart.setValue(item);itemPart.commit();partIndex++}if(partIndex<itemParts.length){itemParts.length=partIndex;this.clear(itemPart&&itemPart.endNode)}}clear(startNode=this.startNode){removeNodes(this.startNode.parentNode,startNode.nextSibling,this.endNode)}}class BooleanAttributePart{constructor(element,name,strings){this.value=undefined;this.__pendingValue=undefined;if(strings.length!==2||strings[0]!==""||strings[1]!==""){throw new Error("Boolean attributes can only contain a single expression")}this.element=element;this.name=name;this.strings=strings}setValue(value){this.__pendingValue=value}commit(){while(isDirective(this.__pendingValue)){const directive=this.__pendingValue;this.__pendingValue=noChange;directive(this)}if(this.__pendingValue===noChange){return}const value=!!this.__pendingValue;if(this.value!==value){if(value){this.element.setAttribute(this.name,"")}else{this.element.removeAttribute(this.name)}this.value=value}this.__pendingValue=noChange}}class PropertyCommitter extends AttributeCommitter{constructor(element,name,strings){super(element,name,strings);this.single=strings.length===2&&strings[0]===""&&strings[1]===""}_createPart(){return new PropertyPart(this)}_getValue(){if(this.single){return this.parts[0].value}return super._getValue()}commit(){if(this.dirty){this.dirty=false;this.element[this.name]=this._getValue()}}}class PropertyPart extends AttributePart{}let eventOptionsSupported=false;(()=>{try{const options={get capture(){eventOptionsSupported=true;return false}};window.addEventListener("test",options,options);window.removeEventListener("test",options,options)}catch(_e){}})();class EventPart{constructor(element,eventName,eventContext){this.value=undefined;this.__pendingValue=undefined;this.element=element;this.eventName=eventName;this.eventContext=eventContext;this.__boundHandleEvent=e=>this.handleEvent(e)}setValue(value){this.__pendingValue=value}commit(){while(isDirective(this.__pendingValue)){const directive=this.__pendingValue;this.__pendingValue=noChange;directive(this)}if(this.__pendingValue===noChange){return}const newListener=this.__pendingValue;const oldListener=this.value;const shouldRemoveListener=newListener==null||oldListener!=null&&(newListener.capture!==oldListener.capture||newListener.once!==oldListener.once||newListener.passive!==oldListener.passive);const shouldAddListener=newListener!=null&&(oldListener==null||shouldRemoveListener);if(shouldRemoveListener){this.element.removeEventListener(this.eventName,this.__boundHandleEvent,this.__options)}if(shouldAddListener){this.__options=getOptions(newListener);this.element.addEventListener(this.eventName,this.__boundHandleEvent,this.__options)}this.value=newListener;this.__pendingValue=noChange}handleEvent(event){if(typeof this.value==="function"){this.value.call(this.eventContext||this.element,event)}else{this.value.handleEvent(event)}}}const getOptions=o=>o&&(eventOptionsSupported?{capture:o.capture,passive:o.passive,once:o.once}:o.capture);function templateFactory(result){let templateCache=templateCaches.get(result.type);if(templateCache===undefined){templateCache={stringsArray:new WeakMap,keyString:new Map};templateCaches.set(result.type,templateCache)}let template=templateCache.stringsArray.get(result.strings);if(template!==undefined){return template}const key=result.strings.join(marker);template=templateCache.keyString.get(key);if(template===undefined){template=new Template(result,result.getTemplateElement());templateCache.keyString.set(key,template)}templateCache.stringsArray.set(result.strings,template);return template}const templateCaches=new Map;const parts=new WeakMap;const render$1=(result,container,options)=>{let part=parts.get(container);if(part===undefined){removeNodes(container,container.firstChild);parts.set(container,part=new NodePart(Object.assign({templateFactory:templateFactory},options)));part.appendInto(container)}part.setValue(result);part.commit()};class DefaultTemplateProcessor{handleAttributeExpressions(element,name,strings,options){const prefix=name[0];if(prefix==="."){const committer=new PropertyCommitter(element,name.slice(1),strings);return committer.parts}if(prefix==="@"){return[new EventPart(element,name.slice(1),options.eventContext)]}if(prefix==="?"){return[new BooleanAttributePart(element,name.slice(1),strings)]}const committer=new AttributeCommitter(element,name,strings);return committer.parts}handleTextExpression(options){return new NodePart(options)}}const defaultTemplateProcessor=new DefaultTemplateProcessor;if(typeof window!=="undefined"){(window["litHtmlVersions"]||(window["litHtmlVersions"]=[])).push("1.4.1")}const html=(strings,...values)=>new TemplateResult(strings,values,"html",defaultTemplateProcessor);const getTemplateCacheKey=(type,scopeName)=>`${type}--${scopeName}`;let compatibleShadyCSSVersion=true;if(typeof window.ShadyCSS==="undefined"){compatibleShadyCSSVersion=false}else if(typeof window.ShadyCSS.prepareTemplateDom==="undefined"){console.warn(`Incompatible ShadyCSS version detected. `+`Please update to at least @webcomponents/webcomponentsjs@2.0.2 and `+`@webcomponents/shadycss@1.3.1.`);compatibleShadyCSSVersion=false}const shadyTemplateFactory=scopeName=>result=>{const cacheKey=getTemplateCacheKey(result.type,scopeName);let templateCache=templateCaches.get(cacheKey);if(templateCache===undefined){templateCache={stringsArray:new WeakMap,keyString:new Map};templateCaches.set(cacheKey,templateCache)}let template=templateCache.stringsArray.get(result.strings);if(template!==undefined){return template}const key=result.strings.join(marker);template=templateCache.keyString.get(key);if(template===undefined){const element=result.getTemplateElement();if(compatibleShadyCSSVersion){window.ShadyCSS.prepareTemplateDom(element,scopeName)}template=new Template(result,element);templateCache.keyString.set(key,template)}templateCache.stringsArray.set(result.strings,template);return template};const TEMPLATE_TYPES=["html","svg"];const removeStylesFromLitTemplates=scopeName=>{TEMPLATE_TYPES.forEach((type=>{const templates=templateCaches.get(getTemplateCacheKey(type,scopeName));if(templates!==undefined){templates.keyString.forEach((template=>{const{element:{content:content}}=template;const styles=new Set;Array.from(content.querySelectorAll("style")).forEach((s=>{styles.add(s)}));removeNodesFromTemplate(template,styles)}))}}))};const shadyRenderSet=new Set;const prepareTemplateStyles=(scopeName,renderedDOM,template)=>{shadyRenderSet.add(scopeName);const templateElement=!!template?template.element:document.createElement("template");const styles=renderedDOM.querySelectorAll("style");const{length:length}=styles;if(length===0){window.ShadyCSS.prepareTemplateStyles(templateElement,scopeName);return}const condensedStyle=document.createElement("style");for(let i=0;i<length;i++){const style=styles[i];style.parentNode.removeChild(style);condensedStyle.textContent+=style.textContent}removeStylesFromLitTemplates(scopeName);const content=templateElement.content;if(!!template){insertNodeIntoTemplate(template,condensedStyle,content.firstChild)}else{content.insertBefore(condensedStyle,content.firstChild)}window.ShadyCSS.prepareTemplateStyles(templateElement,scopeName);const style=content.querySelector("style");if(window.ShadyCSS.nativeShadow&&style!==null){renderedDOM.insertBefore(style.cloneNode(true),renderedDOM.firstChild)}else if(!!template){content.insertBefore(condensedStyle,content.firstChild);const removes=new Set;removes.add(condensedStyle);removeNodesFromTemplate(template,removes)}};const render=(result,container,options)=>{if(!options||typeof options!=="object"||!options.scopeName){throw new Error("The `scopeName` option is required.")}const scopeName=options.scopeName;const hasRendered=parts.has(container);const needsScoping=compatibleShadyCSSVersion&&container.nodeType===11&&!!container.host;const firstScopeRender=needsScoping&&!shadyRenderSet.has(scopeName);const renderContainer=firstScopeRender?document.createDocumentFragment():container;render$1(result,renderContainer,Object.assign({templateFactory:shadyTemplateFactory(scopeName)},options));if(firstScopeRender){const part=parts.get(renderContainer);parts.delete(renderContainer);const template=part.value instanceof TemplateInstance?part.value.template:undefined;prepareTemplateStyles(scopeName,renderContainer,template);removeNodes(container,container.firstChild);container.appendChild(renderContainer);parts.set(container,part)}if(!hasRendered&&needsScoping){window.ShadyCSS.styleElement(container.host)}};var _a;window.JSCompiler_renameProperty=(prop,_obj)=>prop;const defaultConverter={toAttribute(value,type){switch(type){case Boolean:return value?"":null;case Object:case Array:return value==null?value:JSON.stringify(value)}return value},fromAttribute(value,type){switch(type){case Boolean:return value!==null;case Number:return value===null?null:Number(value);case Object:case Array:return JSON.parse(value)}return value}};const notEqual=(value,old)=>old!==value&&(old===old||value===value);const defaultPropertyDeclaration={attribute:true,type:String,converter:defaultConverter,reflect:false,hasChanged:notEqual};const STATE_HAS_UPDATED=1;const STATE_UPDATE_REQUESTED=1<<2;const STATE_IS_REFLECTING_TO_ATTRIBUTE=1<<3;const STATE_IS_REFLECTING_TO_PROPERTY=1<<4;const finalized="finalized";class UpdatingElement extends HTMLElement{constructor(){super();this.initialize()}static get observedAttributes(){this.finalize();const attributes=[];this._classProperties.forEach(((v,p)=>{const attr=this._attributeNameForProperty(p,v);if(attr!==undefined){this._attributeToPropertyMap.set(attr,p);attributes.push(attr)}}));return attributes}static _ensureClassProperties(){if(!this.hasOwnProperty(JSCompiler_renameProperty("_classProperties",this))){this._classProperties=new Map;const superProperties=Object.getPrototypeOf(this)._classProperties;if(superProperties!==undefined){superProperties.forEach(((v,k)=>this._classProperties.set(k,v)))}}}static createProperty(name,options=defaultPropertyDeclaration){this._ensureClassProperties();this._classProperties.set(name,options);if(options.noAccessor||this.prototype.hasOwnProperty(name)){return}const key=typeof name==="symbol"?Symbol():`__${name}`;const descriptor=this.getPropertyDescriptor(name,key,options);if(descriptor!==undefined){Object.defineProperty(this.prototype,name,descriptor)}}static getPropertyDescriptor(name,key,options){return{get(){return this[key]},set(value){const oldValue=this[name];this[key]=value;this.requestUpdateInternal(name,oldValue,options)},configurable:true,enumerable:true}}static getPropertyOptions(name){return this._classProperties&&this._classProperties.get(name)||defaultPropertyDeclaration}static finalize(){const superCtor=Object.getPrototypeOf(this);if(!superCtor.hasOwnProperty(finalized)){superCtor.finalize()}this[finalized]=true;this._ensureClassProperties();this._attributeToPropertyMap=new Map;if(this.hasOwnProperty(JSCompiler_renameProperty("properties",this))){const props=this.properties;const propKeys=[...Object.getOwnPropertyNames(props),...typeof Object.getOwnPropertySymbols==="function"?Object.getOwnPropertySymbols(props):[]];for(const p of propKeys){this.createProperty(p,props[p])}}}static _attributeNameForProperty(name,options){const attribute=options.attribute;return attribute===false?undefined:typeof attribute==="string"?attribute:typeof name==="string"?name.toLowerCase():undefined}static _valueHasChanged(value,old,hasChanged=notEqual){return hasChanged(value,old)}static _propertyValueFromAttribute(value,options){const type=options.type;const converter=options.converter||defaultConverter;const fromAttribute=typeof converter==="function"?converter:converter.fromAttribute;return fromAttribute?fromAttribute(value,type):value}static _propertyValueToAttribute(value,options){if(options.reflect===undefined){return}const type=options.type;const converter=options.converter;const toAttribute=converter&&converter.toAttribute||defaultConverter.toAttribute;return toAttribute(value,type)}initialize(){this._updateState=0;this._updatePromise=new Promise((res=>this._enableUpdatingResolver=res));this._changedProperties=new Map;this._saveInstanceProperties();this.requestUpdateInternal()}_saveInstanceProperties(){this.constructor._classProperties.forEach(((_v,p)=>{if(this.hasOwnProperty(p)){const value=this[p];delete this[p];if(!this._instanceProperties){this._instanceProperties=new Map}this._instanceProperties.set(p,value)}}))}_applyInstanceProperties(){this._instanceProperties.forEach(((v,p)=>this[p]=v));this._instanceProperties=undefined}connectedCallback(){this.enableUpdating()}enableUpdating(){if(this._enableUpdatingResolver!==undefined){this._enableUpdatingResolver();this._enableUpdatingResolver=undefined}}disconnectedCallback(){}attributeChangedCallback(name,old,value){if(old!==value){this._attributeToProperty(name,value)}}_propertyToAttribute(name,value,options=defaultPropertyDeclaration){const ctor=this.constructor;const attr=ctor._attributeNameForProperty(name,options);if(attr!==undefined){const attrValue=ctor._propertyValueToAttribute(value,options);if(attrValue===undefined){return}this._updateState=this._updateState|STATE_IS_REFLECTING_TO_ATTRIBUTE;if(attrValue==null){this.removeAttribute(attr)}else{this.setAttribute(attr,attrValue)}this._updateState=this._updateState&~STATE_IS_REFLECTING_TO_ATTRIBUTE}}_attributeToProperty(name,value){if(this._updateState&STATE_IS_REFLECTING_TO_ATTRIBUTE){return}const ctor=this.constructor;const propName=ctor._attributeToPropertyMap.get(name);if(propName!==undefined){const options=ctor.getPropertyOptions(propName);this._updateState=this._updateState|STATE_IS_REFLECTING_TO_PROPERTY;this[propName]=ctor._propertyValueFromAttribute(value,options);this._updateState=this._updateState&~STATE_IS_REFLECTING_TO_PROPERTY}}requestUpdateInternal(name,oldValue,options){let shouldRequestUpdate=true;if(name!==undefined){const ctor=this.constructor;options=options||ctor.getPropertyOptions(name);if(ctor._valueHasChanged(this[name],oldValue,options.hasChanged)){if(!this._changedProperties.has(name)){this._changedProperties.set(name,oldValue)}if(options.reflect===true&&!(this._updateState&STATE_IS_REFLECTING_TO_PROPERTY)){if(this._reflectingProperties===undefined){this._reflectingProperties=new Map}this._reflectingProperties.set(name,options)}}else{shouldRequestUpdate=false}}if(!this._hasRequestedUpdate&&shouldRequestUpdate){this._updatePromise=this._enqueueUpdate()}}requestUpdate(name,oldValue){this.requestUpdateInternal(name,oldValue);return this.updateComplete}async _enqueueUpdate(){this._updateState=this._updateState|STATE_UPDATE_REQUESTED;try{await this._updatePromise}catch(e){}const result=this.performUpdate();if(result!=null){await result}return!this._hasRequestedUpdate}get _hasRequestedUpdate(){return this._updateState&STATE_UPDATE_REQUESTED}get hasUpdated(){return this._updateState&STATE_HAS_UPDATED}performUpdate(){if(!this._hasRequestedUpdate){return}if(this._instanceProperties){this._applyInstanceProperties()}let shouldUpdate=false;const changedProperties=this._changedProperties;try{shouldUpdate=this.shouldUpdate(changedProperties);if(shouldUpdate){this.update(changedProperties)}else{this._markUpdated()}}catch(e){shouldUpdate=false;this._markUpdated();throw e}if(shouldUpdate){if(!(this._updateState&STATE_HAS_UPDATED)){this._updateState=this._updateState|STATE_HAS_UPDATED;this.firstUpdated(changedProperties)}this.updated(changedProperties)}}_markUpdated(){this._changedProperties=new Map;this._updateState=this._updateState&~STATE_UPDATE_REQUESTED}get updateComplete(){return this._getUpdateComplete()}_getUpdateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._updatePromise}shouldUpdate(_changedProperties){return true}update(_changedProperties){if(this._reflectingProperties!==undefined&&this._reflectingProperties.size>0){this._reflectingProperties.forEach(((v,k)=>this._propertyToAttribute(k,this[k],v)));this._reflectingProperties=undefined}this._markUpdated()}updated(_changedProperties){}firstUpdated(_changedProperties){}}_a=finalized;UpdatingElement[_a]=true;const supportsAdoptingStyleSheets=window.ShadowRoot&&(window.ShadyCSS===undefined||window.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype;const constructionToken=Symbol();class CSSResult{constructor(cssText,safeToken){if(safeToken!==constructionToken){throw new Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.")}this.cssText=cssText}get styleSheet(){if(this._styleSheet===undefined){if(supportsAdoptingStyleSheets){this._styleSheet=new CSSStyleSheet;this._styleSheet.replaceSync(this.cssText)}else{this._styleSheet=null}}return this._styleSheet}toString(){return this.cssText}}const unsafeCSS=value=>new CSSResult(String(value),constructionToken);const textFromCSSResult=value=>{if(value instanceof CSSResult){return value.cssText}else if(typeof value==="number"){return value}else{throw new Error(`Value passed to 'css' function must be a 'css' function result: ${value}. Use 'unsafeCSS' to pass non-literal values, but\n            take care to ensure page security.`)}};const css=(strings,...values)=>{const cssText=values.reduce(((acc,v,idx)=>acc+textFromCSSResult(v)+strings[idx+1]),strings[0]);return new CSSResult(cssText,constructionToken)};(window["litElementVersions"]||(window["litElementVersions"]=[])).push("2.5.1");const renderNotImplemented={};class LitElement extends UpdatingElement{static getStyles(){return this.styles}static _getUniqueStyles(){if(this.hasOwnProperty(JSCompiler_renameProperty("_styles",this))){return}const userStyles=this.getStyles();if(Array.isArray(userStyles)){const addStyles=(styles,set)=>styles.reduceRight(((set,s)=>Array.isArray(s)?addStyles(s,set):(set.add(s),set)),set);const set=addStyles(userStyles,new Set);const styles=[];set.forEach((v=>styles.unshift(v)));this._styles=styles}else{this._styles=userStyles===undefined?[]:[userStyles]}this._styles=this._styles.map((s=>{if(s instanceof CSSStyleSheet&&!supportsAdoptingStyleSheets){const cssText=Array.prototype.slice.call(s.cssRules).reduce(((css,rule)=>css+rule.cssText),"");return unsafeCSS(cssText)}return s}))}initialize(){super.initialize();this.constructor._getUniqueStyles();this.renderRoot=this.createRenderRoot();if(window.ShadowRoot&&this.renderRoot instanceof window.ShadowRoot){this.adoptStyles()}}createRenderRoot(){return this.attachShadow(this.constructor.shadowRootOptions)}adoptStyles(){const styles=this.constructor._styles;if(styles.length===0){return}if(window.ShadyCSS!==undefined&&!window.ShadyCSS.nativeShadow){window.ShadyCSS.ScopingShim.prepareAdoptedCssText(styles.map((s=>s.cssText)),this.localName)}else if(supportsAdoptingStyleSheets){this.renderRoot.adoptedStyleSheets=styles.map((s=>s instanceof CSSStyleSheet?s:s.styleSheet))}else{this._needsShimAdoptedStyleSheets=true}}connectedCallback(){super.connectedCallback();if(this.hasUpdated&&window.ShadyCSS!==undefined){window.ShadyCSS.styleElement(this)}}update(changedProperties){const templateResult=this.render();super.update(changedProperties);if(templateResult!==renderNotImplemented){this.constructor.render(templateResult,this.renderRoot,{scopeName:this.localName,eventContext:this})}if(this._needsShimAdoptedStyleSheets){this._needsShimAdoptedStyleSheets=false;this.constructor._styles.forEach((s=>{const style=document.createElement("style");style.textContent=s.cssText;this.renderRoot.appendChild(style)}))}}render(){return renderNotImplemented}}LitElement["finalized"]=true;LitElement.render=render;LitElement.shadowRootOptions={mode:"open"};

// ======================================================================
//  Absolute Forecast Card  (без внешних import-ов)
// ======================================================================

// карта иконок штатных атрибутов из core/src/data/weather.ts
// 
const weatherAttrIcons = {
  // штатные атрибуты погоды
  apparent_temperature: "mdi:thermometer",
  cloud_coverage:       "mdi:cloud-percent-outline",
  dew_point:            "mdi:water-thermometer-outline",
  humidity:             "mdi:water-percent",
  wind_bearing:         "mdi:weather-windy",
  wind_speed:           "mdi:weather-windy",
  pressure:             "mdi:gauge",
  temperature:          "mdi:thermometer",
  uv_index:             "mdi:sun-wireless",
  visibility:           "mdi:eye-outline",
  precipitation:        "mdi:weather-rainy",

  // иконки для аллергенов (pollen_*)
  pollen_alder:   "mdi:tree",
  pollen_birch:   "mdi:tree-outline",
  pollen_grass:   "mdi:grass",
  pollen_hazel:   "mdi:hops",
  pollen_mugwort: "mdi:barley",
  pollen_olive:   "mdi:grain",
  pollen_ragweed: "mdi:barley",
  // индекс текущего прогноза
  responsible_elevated:      "mdi:flower-pollen",
  // если у вас есть поле для «следующего» индекса
  next_condition: "mdi:clock-alert-outline",

  // добавленные по запросу
  ozone:     "mdi:hexagon-multiple-outline",
  wind_gust_speed: "mdi:weather-dust",
};

// ======================================================================
//  Шкалы пыльцы и соответствующие цвета
// ======================================================================
// Общие цвета для всех видов
const POLLEN_COLORS = [
  "rgb(222,222,222)",
  "rgb(0,222,0)",
  "rgb(171,239,48)",
  "rgb(239,222,48)",
  "rgb(239,172,28)",
  "rgb(255,137,28)",
  "rgb(255,48,48)",
  "rgb(255,0,137)",
  "rgb(171,0,205)",
];

// Матрица: каждая запись — список видов + их пороги
const SCALE_DEFS = [
  {
    species: ["birch", "grass", "hazel"],
    thresholds: [1, 5, 10, 25, 50, 100, 500, 1000, 5000],
  },
  {
    species: ["alder", "olive", "mugwort", "ragweed"],
    thresholds: [0.1, 1, 5, 10, 25, 50, 100, 500, 1000],
  },
];

// Собираем финальную константу автоматически
const POLLEN_SCALES = Object.fromEntries(
  SCALE_DEFS.flatMap(({ species, thresholds }) =>
    species.map(sp => [
      sp,
      { thresholds, colors: POLLEN_COLORS }
    ])
  )
);

const BAR_CHART_HEIGHT = 70;      // общая высота “столбика” в пикселях
const POLLEN_SEGMENTS = SCALE_DEFS[0].thresholds.length;

// Пример результата:
// {
//   birch: { thresholds: [...], colors: [...] },
//   grass: { thresholds: [...], colors: [...] },
//   ...
// }

// Функция маппинга температуры в цвет от холодного к тёплому
/**
 * -40..0 → 280°→180° (фиолетовый→циан) — линейно
 *  0..+40 → 180°→0° (циан→красный) — с экспонентой 0.5
 */
function mapTempToColor(temp) {
  const t = Math.max(-40, Math.min(40, temp));
  if (t <= 0) {
    // холодный диапазон: линейно
    const ratio = (t + 40) / 40;      // 0..1
    const hue   = 280 - ratio * 100;  // 280→180
    return `hsl(${hue},100%,50%)`;
  } else {
    // тёплый диапазон: быстрее сбрасываем к красному
    const ratio = t / 40;       
    const adj   = Math.pow(ratio, 0.6);   // экспонента <1 → резче в начале
    const hue   = 180 - adj * 180;        // 180→0, но «зелёная» зона очень узкая
    return `hsl(${hue},100%,50%)`;
  }
}

/* ---------- флаги supported_features из core/data/weather.ts ---------- */
const FORECAST_DAILY       = 1;  // WeatherEntityFeature.FORECAST_DAILY
const FORECAST_HOURLY      = 2;  // WeatherEntityFeature.FORECAST_HOURLY
const FORECAST_TWICE_DAILY = 4;  // WeatherEntityFeature.FORECAST_TWICE_DAILY

function forecastSupported(stateObj, type) {
  if (!stateObj) return false;
  const flags = stateObj.attributes?.supported_features ?? 0;
  switch (type) {
    case "hourly":      return (flags & FORECAST_HOURLY)      !== 0;
    case "daily":       return (flags & FORECAST_DAILY)       !== 0;
    case "twice_daily": return (flags & FORECAST_TWICE_DAILY) !== 0;
    default:            return false;
  }
}

// -------------------------------------------------------------
//  Мини-реализация resolveTimeZone + кэш браузерного пояса
// -------------------------------------------------------------
const BROWSER_TZ =
  Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";

/**
 * option : "local" | "server"
 * serverTZ : строка-IANA из configuration.yaml
 *
 *  • "local"  → возвращаем TZ браузера
 *  • иначе    → возвращаем serverTZ
 */
function resolveTimeZone(option, serverTZ) {
  return option === "local" ? BROWSER_TZ : serverTZ;
}

/** Обёртка: добавляем корректный timeZone, если он есть */
function withUserTimeZone(hass, opts = {}) {
  const option   = hass.locale?.time_zone;   // "local" | "server" | undefined
  const serverTZ = hass.config?.time_zone;   // строка-IANA
  const tz       = resolveTimeZone(option, serverTZ);
  return tz ? { ...opts, timeZone: tz } : opts;
}

class AbsoluteForecastCard extends HTMLElement {
  /* ---------- конфигурация ---------- */
  setConfig(cfg) {
    if (!cfg || !cfg.entity)
      throw new Error("absolute-forecast-card: 'entity' is required");
    // добавили display_attribute
    this._cfg = {
      forecast_type: "hourly",
      only_silam: true,
      display_attribute: "",
      additional_forecast_mode: "standard",
      ...cfg
    };
    // новый переключатель: показывать только дополнительный блок
    this._cfg.additional_only = this._cfg.additional_only || false;
    this._initDom();
  }

  // ─── Начало: хелперы форматирования чисел из Home Assistant ───
  /** 
   * Выбирает правильную локаль(и) для Intl.NumberFormat 
   * (из frontend/src/common/number/format_number.ts) :contentReference[oaicite:0]{index=0}
   */
  _numberFormatToLocale(localeOptions) {
    switch (localeOptions.number_format) {
      case "comma_decimal":   return ["en-US", "en"];      // 1,234,567.89
      case "decimal_comma":   return ["de", "es", "it"];    // 1.234.567,89
      case "space_comma":     return ["fr", "sv", "cs"];    // 1 234 567,89
      case "system":          return undefined;             // использовать browser default
      default:                return localeOptions.language;
    }
  }

  /**
   * Генерирует опции для Intl.NumberFormat 
   * (из frontend/src/common/number/format_number.ts) :contentReference[oaicite:1]{index=1}
   */
  _getDefaultFormatOptions(num, options) {
    const defaultOpts = { maximumFractionDigits: 2, ...options };
    if (typeof num !== "string") return defaultOpts;
    if (
      !options ||
      (options.minimumFractionDigits === undefined &&
       options.maximumFractionDigits === undefined)
    ) {
      const digits = num.includes(".") ? num.split(".")[1].length : 0;
      defaultOpts.minimumFractionDigits = digits;
      defaultOpts.maximumFractionDigits = digits;
    }
    return defaultOpts;
  }

  /**
   * Основная функция форматирования числа по user-настройкам 
   * (из frontend/src/common/number/format_number.ts) :contentReference[oaicite:2]{index=2}
   */
  _formatNumberInternal(num, localeOptions, options) {
    const locale = this._numberFormatToLocale(localeOptions);
    // если включено форматирование и число валидно
    if (
      localeOptions.number_format !== "none" &&
      !Number.isNaN(Number(num))
    ) {
      return new Intl.NumberFormat(
        locale,
        this._getDefaultFormatOptions(num, options)
      ).format(Number(num));
    }
    // если отключено группирование, но валидно
    if (
      !Number.isNaN(Number(num)) &&
      localeOptions.number_format === "none"
    ) {
      return new Intl.NumberFormat(
        "en-US",
        this._getDefaultFormatOptions(num, { ...options, useGrouping: false })
      ).format(Number(num));
    }
    // если строка — возвращаем как есть
    if (typeof num === "string") {
      return num;
    }
    // fallback: ручное округление и добавление currency-юнита
    const rounded = Math.round(
      Number(num) *
        Math.pow(
          10,
          options?.maximumFractionDigits != null
            ? options.maximumFractionDigits
            : 0
        )
    ) /
      Math.pow(
        10,
        options?.maximumFractionDigits != null
          ? options.maximumFractionDigits
          : 0
      );
    return (
      rounded.toString() +
      (options?.style === "currency" ? ` ${options.currency}` : "")
    );
  }
  // ─── Конец хелперов ───

  /* ---------- Home Assistant ---------- */
  set hass(hass) {
    if (!hass) return;
    this._hass = hass;
    if (!this._ready) {
      this._initLocalization();
      this._subscribe();
      this._ready = true;
    }
  }
  get hass() { return this._hass; }

  /* ---------- DOM ---------- */
  _initDom() {
    if (this.shadowRoot) return;
    this.attachShadow({ mode: "open" });
    this.shadowRoot.innerHTML = `
      <ha-card>
        <div id="body" style="padding:16px">Loading…</div>
      </ha-card>`;
    this._body   = this.shadowRoot.getElementById("body");
  }

  /* ---------- локализация ---------- */
  _t(key) {
    const res  = this._hass.resources;
    const lang = this._hass.language || "en";
    return (res?.[lang]?.[key]) || (res?.en?.[key]);
  }
  _initLocalization() {
    const p = "component.silam_pollen.entity.sensor.";
    const list = ["alder","birch","grass","hazel","mugwort","olive","ragweed"];
    this._labels = {};
    list.forEach(n=>{
      this._labels["pollen_"+n] =
        this._t(`${p}${n}.name`) || n.charAt(0).toUpperCase()+n.slice(1);
    });
    this._indexLbl =
      this._t("component.silam_pollen.entity.sensor.index.name") || "Index";
    const base = "component.silam_pollen.entity.sensor.index.state.";
    this._cond = {};
    ["very_low","low","moderate","high","very_high","unknown"]
      .forEach(s=>this._cond[s] = this._t(base+s) || s);
  }

  /* ---------- WebSocket-подписка ---------- */
  _subscribe() {
    this._unsubP = this._hass.connection.subscribeMessage(
      ev => this._renderList(ev.forecast),
      {
        type: "weather/subscribe_forecast",
        entity_id: this._cfg.entity,
        forecast_type: this._cfg.forecast_type,
      }
    ).then(fn => this._unsub = fn);
  }
  disconnectedCallback() {
    const safe = fn => typeof fn==="function" && fn().catch(()=>{});
    this._unsub ? safe(this._unsub)
      : this._unsubP && this._unsubP.then(safe);
  }

  /**
   * Возвращает mdi-иконку для атрибута, или ничего.
   */
  _computeAttributeIcon(attr) {
    return weatherAttrIcons[attr] || null;
  }
  
  /**
   * Возвращает <span class="value-flex">,
   * внутри двух элементов:
   *   [ha-icon] [текст]
   */
  _createAttributeValueEl(key, stateObj) {
    const value = this._hass.formatEntityAttributeValue(stateObj, key) || "";
    const iconName = this._computeAttributeIcon(key); 
    // общий контейнер с flex-классом
    const wrapper = document.createElement("span");
    wrapper.classList.add("value-flex");
    // иконка (если есть)
    if (iconName) {
      const iconEl = document.createElement("ha-icon");
      iconEl.icon = iconName;
      // вот здесь сразу всё вместе
      iconEl.style.cssText = `
        display: inline-flex;
        --mdc-icon-size: 1.35em;
        margin-right: 6px;
      `;
      wrapper.appendChild(iconEl);
    }
    // текст  
    wrapper.appendChild(document.createTextNode(value));
    return wrapper;
  }

  /**
   * Создаёт и стилизует общий контейнер для дополнительного блока
   * @param {string} mode — текущий режим additional_forecast_mode
   * @returns {HTMLDivElement}
   */
  _createBlockContainer(mode) {
    const block = document.createElement("div");
    block.style.cssText = `
      display: flex;
      flex-direction: ${mode === "focus" ? "column" : "column"};
      align-items: ${mode === "focus" ? "stretch" : "stretch"};
      gap: ${mode === "focus" ? "0px" : "0px"};
      width: 100%;
      box-sizing: border-box;
      padding: ${mode === "focus" ? "4px 0" : "12px 0"};
      ${mode === "focus" ? `
        /* background: var(--secondary-background-color);
        border-radius: 6px;
      ` : ``}
    `;
    return block;
  }

  /**
   * Создаёт и стилизует обёртку блока с grid‐лейаутом
   * @param {"standard"|"focus"} mode
   * @param {boolean} includeTitle — показывать ли зону для title
   * @returns {HTMLDivElement}
   */
  _createBlockWrapper(mode, includeTitle = true) {
    const wrapper = document.createElement("div");
    wrapper.classList.add("block-wrapper", mode);

    // общие свойства
    let gap       = mode === "focus" ? "2px" : "4px";
    let cols, rows, areas, colGap = "";

    if (mode === "focus") {
      // focus — одна колонка
      cols  = "1fr";
      rows  = includeTitle ? "auto auto 1fr" : "auto 1fr";
      areas = includeTitle
        ? `"title" "header" "bars"`
        : `"header" "bars"`;
    } else {
      // standard — две колонки
      cols  = "auto 1fr";
      rows  = includeTitle ? "auto auto" : "auto";
      areas = includeTitle
        ? `"title bars" "header bars"`
        : `"header bars"`;
      colGap = "column-gap: 3%; align-items: center;";
    }

    wrapper.style.cssText = `
      display: grid;
      width: 100%;
      box-sizing: border-box;

      /* layout */
      grid-template-areas: ${areas};
      grid-template-columns: ${cols};
      grid-template-rows: ${rows};

      /* gaps */
      gap: ${gap};
      ${colGap}
    `;

    return wrapper;
  }

  /**
   * Создаёт контейнер для произвольного «title» над header и гистограммой
   * @param {"standard"|"focus"} mode – текущий режим additional_forecast_mode
   * @returns {HTMLDivElement}
   */
  _createTitleContainer(mode) {
    const container = document.createElement("div");
    container.classList.add("block-title");
    container.style.cssText = `
      display: inline-flex;
      line-height: 1;
      /* размер шрифта чуть меньше в фокусе, чуть больше в стандартном */
      font-size: ${mode === "focus" ? "1em" : "1.2em"};
      ${mode === "focus"
        ? ``
        : `justify-content: center;
          align-items: center;`
      }
    `;
    return container;
  }

  /**
   * Создаёт и стилизует контейнер header для любого дополнительного блока
   * @param {string} mode — текущий режим additional_forecast_mode
   * @returns {HTMLDivElement}
   */
  _createHeaderContainer(mode) {
    const header = document.createElement("div");
    header.style.cssText = `
      display: flex;
      flex-direction: ${mode === "focus" ? "row"    : "column"};
      align-items: ${mode === "focus" ? "": ""};
      gap:           ${mode === "focus" ? "4px"    : "4px"};
      ${mode === "focus"
        ? `width: 100%; margin-bottom: 2px;`
        : `width: 25%; min-width: 126px;`
      }
    `;
    return header;
  }

  /**
   * Создаёт и стилизует контейнер для текущего значения и статистики (min/max)
   * @param {string} mode — текущий режим additional_forecast_mode
   * @returns {HTMLDivElement}
   */
  _createValueContainer(mode) {
    const container = document.createElement("div");
    container.style.cssText = `
        display: inline-flex;
        flex-direction: ${mode === "focus" ? "row" : "column"};
        line-height: ${mode === "focus" ? "1" : ""};
        gap: ${mode === "focus" ? "2px" : "1px"};
        align-items: ${mode === "focus" ? "flex-end" : "flex-end"};
        justify-content: center;
    `;
    return container;
  }

  /**
   * Вынесём создание flex-контейнера для любых секций (base-info, peak-info и т.д.)
   * @param {string} className — CSS-класс для контейнера
   * @param {"standard"|"focus"} mode — режим карточки
   * @param {string} [customStyles] — опциональные дополнительные inline-стили
   * @returns {HTMLDivElement}
   */
  _createSectionContainer(className, mode, customStyles = "") {
    const container = document.createElement("div");
    container.classList.add(className);
    container.style.cssText = `
      display: flex;
      align-items: ${mode === "focus" ? "flex-end" : "center"};
      gap: ${mode === "focus"
        ? "4px"
        : "clamp(2px, 4%, 8px)"
      };
      ${mode === "focus" ? `` : `flex-wrap: nowrap;`}
      ${customStyles}
    `;
    return container;
  }

  /**    
   * Создаёт div с подписью времени/дня/дня+части для прогноза.
   * @param {{ datetime: string; is_daytime?: boolean }} item
   * @param {"hourly"|"daily"|"twice_daily"} forecastType
   * @param {{ timeFontSize: string; timeFontWeight: string; timeMarginBottom: string; partFontSize?: string; partColor?: string }} opts
   * @returns {HTMLDivElement|DocumentFragment}
   */
  _createTimeLabel(item, forecastType, opts) {
    const dt = new Date(item.datetime);

  // hourly: показываем минуты только если ширина ячейки позволяет
  if (forecastType === "hourly") {
    const el = document.createElement("div");
    const dt = new Date(item.datetime);

    // Общие стили
    el.style.cssText = `
      text-align: center;
      color: var(--primary-text-color);
      line-height: 1;
    `;

    // Функция обновления текста в зависимости от ширины
    const updateText = () => {
      // порог в пикселях, при котором можно уместить "HH:MM"
      const threshold = 40;
      const showMinutes = el.clientWidth > threshold;
      const timeOptions = showMinutes
        ? { hour: "2-digit", minute: "2-digit" }
        : { hour: "2-digit" };

      el.textContent = dt.toLocaleTimeString(
        this.hass.language,
        withUserTimeZone(this.hass, timeOptions)
      );
      // после отрисовки задаём стили шрифта и нижнего отступа
      el.style.fontSize     = opts.timeFontSize;
      el.style.fontWeight   = opts.timeFontWeight;
      el.style.marginBottom = opts.timeMarginBottom;
    };

    // Наблюдаем изменения размера элемента
    const ro = new ResizeObserver(updateText);
    ro.observe(el);

    // Первая установка текста
    updateText();

    return el;
  }

    // daily: просто день недели
    if (forecastType === "daily") {
      const el = document.createElement("div");
      el.textContent = dt.toLocaleDateString(
        this.hass.language,
        withUserTimeZone(this.hass, { weekday: "short" })
      );
      el.style.cssText = `
        font-size: ${opts.timeFontSize};
        font-weight: ${opts.timeFontWeight};
        text-align: center;
        margin-bottom: ${opts.timeMarginBottom};
        color: var(--primary-text-color);
        line-height: 1;
      `;
      return el;
    }

    // twice_daily: два ряда: день + часть (день/ночь)
    const weekdayEl = document.createElement("div");
    weekdayEl.textContent = dt.toLocaleDateString(
      this.hass.language,
      withUserTimeZone(this.hass, { weekday: "short" })
    );
    weekdayEl.style.cssText = `
      font-size: ${opts.timeFontSize};
      font-weight: ${opts.timeFontWeight};
      text-align: center;
      margin-bottom: 1px;
      color: var(--primary-text-color);
      line-height: 1;
    `;

    const partEl = document.createElement("div");
    const part = item.is_daytime === false
      ? this.hass.localize("ui.card.weather.night") || "Night"
      : this.hass.localize("ui.card.weather.day")   || "Day";
    partEl.textContent = part;
    partEl.style.cssText = `
      font-size: ${opts.partFontSize || "0.65em"};
      color: ${opts.partColor || "var(--secondary-text-color)"};
      text-align: center;
      margin-bottom: ${opts.timeMarginBottom};
      line-height: 1;
    `;

    const frag = document.createDocumentFragment();
    frag.append(weekdayEl, partEl);
    return frag;
  }

  /**
   * Форматирует день как «сегодня», «завтра» или короткий weekday
   * @param {Date} dt
   * @returns {string}
   */
  _formatRelativeDay(dt) {
    const locale = this.hass.language;
    const today  = new Date();
    today.setHours(0,0,0,0);
    const target = new Date(dt);
    target.setHours(0,0,0,0);
    const diff = Math.round((target - today) / (24*60*60*1000));
    const rtf  = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });

    if (diff === 0 || diff === 1) {
      return rtf.format(diff, "day"); // «сегодня» или «завтра»
    }
    return dt.toLocaleDateString(locale, { weekday: "short" });
  }
  
  // Вспомогательный метод в вашем классе
  _capitalize(text) {
    return text.charAt(0).toUpperCase() + text.slice(1);
  }
  /* ---------- рендер ---------- */
  _renderList(arr) {
    // Inject CSS с clamp() один раз
    if (!this._clampStyleInjected) {
      const style = document.createElement("style");
      style.textContent = `
        .status-text {
          font-size: clamp(1em, 5vw, 2em);
          margin: 0;
          line-height: 0.9;    /* плотный межстрочный интервал */
        }
        .value-flex {
          display: inline-flex;
          align-items: center;
          line-height: 0.9;
        }
        /* по умолчанию: скрываем скролл */
        .hover-scroll {
          overflow-x: auto;
          overflow-y: hidden;
          -webkit-overflow-scrolling: touch;
          scrollbar-width: none;        /* Firefox */
          -ms-overflow-style: none;     /* IE10+ */
        }
        .hover-scroll::-webkit-scrollbar {
          display: none;                /* Chrome/Safari/Edge */
        }

        /* на hover: показываем тонкий скролл */
        .hover-scroll:hover {
          scrollbar-width: thin;        /* Firefox */
        }
        .hover-scroll:hover::-webkit-scrollbar {
          display: block;
          height: 6px;                  /* толщина полосы */
        }
        
        /* Базовые стили */
        .header-container .state-name {
          font-size: clamp(1em, 5vw, 2em);
          white-space: nowrap;           /* пока не переносим */
          overflow-wrap: normal;
        }

        /* Даем право flex-рядкам внутри header контейнеру переноситься, но только когда уж слишком узко */
        .header-container .header-row {
          display: flex;
          flex-direction: row;             /* по умолчанию все в одном ряду */
          gap: 16px;
          align-items: center;
          }
        .header-container .display-info  {
          display: flex;
          flex-direction: row-reverse;
          align-items: center;
          gap: 4px;
          }

        /* Когда контейнер < 600px, разрешаем переносить слова в state-name */
        @container (max-width: 600px) {
          .header-container .state-name {
            white-space: normal;         /* теперь можно переносить */
            overflow-wrap: break-word;
          }
        }

        /* Когда контейнер ещё уже — делаем из flex-ряда колонку */
        @container (max-width: 320px) {
          .header-container .header-row {
            flex-direction: column;
            gap: 4px;
            align-items: flex-start;
            margin-bottom: 4px;
          }
        }
        @container (max-width: 250px) {
          .header-container .header-row-250 {
            flex-direction: column;
            gap: 4px;
          }
        }
        @container (max-width: 320px) {
          .header-container .display-info {
            flex-direction: row;
          }
        }
      .header-container .display-info-text  {
          text-align: right;
          align-items: flex-end;
        }
        @container (max-width: 320px) {
          .header-container .display-info-text {
            text-align: left;
            align-items: flex-start;
          }
        }
      `;
      this.shadowRoot.appendChild(style);
      this._clampStyleInjected = true;
    }

    // Очистка
    this._body.innerHTML = "";
    const stateObj = this._hass.states[this._cfg.entity];
    if (!stateObj) return;
    const mode = this._cfg.forecast; // "show_current" | "show_forecast" | "show_both"
    // Есть ли прогноз?
    const hasForecast = Array.isArray(arr) && arr.length > 0;
    const additionalOnly = Boolean(this._cfg.additional_only);

  // --------------------
  // 1) HEADER (текущая погода)
  // --------------------
    if (mode !== "show_forecast") {
      const header = document.createElement("div");
      header.classList.add("header-container");    // <-- добавили класс
      header.style.cssText = `
        display: flex;
        flex-direction: column;
        /* объявляем контейнер по inline-size (ширине) */
        gap: 8px;
        container-type: inline-size;
      `;

      // GRID: 2 колонки (64px auto 1fr), только горизонтальный gap
      const grid = document.createElement("div");
      grid.classList.add("header-row");
      grid.style.cssText = `
        display: flex;
        width: 100%;
        justify-content: space-between;
      `;

      // 1) Иконка + Имя состояния + friendly_name
      const col1 = document.createElement("div");
      col1.classList.add("header-row-250");
      col1.style.cssText = `
        display: flex;
        gap: 4px;
        min-width: 0;
      `;
      // Иконка 64px
      const iconEl = document.createElement("ha-state-icon");
      iconEl.hass     = this._hass;
      iconEl.stateObj = stateObj;
      iconEl.style.cssText = `
        display: flex;
        --mdc-icon-size: 64px;
        flex: 0 0 64px;
      `;
      // контейнер для Имя состояния + friendly_name
      const col1a = document.createElement("div");
      col1a.style.cssText = `
        display: flex;
        justify-content: center;
        flex-direction: column;
        gap: 4px;
        align-items: baseline;
      `;
      // stateNameEl
      const stateNameEl = document.createElement("div");
      stateNameEl.textContent = this._hass.formatEntityState(stateObj);
      stateNameEl.style.cssText = `
        display: inline-flex;
        white-space: normal;
        font-size: clamp(1em, 5vw, 2em);
        line-height: 0.75;
      `;

      // friendlyEl
      const friendlyEl = document.createElement("div");
      friendlyEl.textContent = stateObj.attributes.friendly_name || "";
      friendlyEl.style.cssText = `
        display: inline-flex;
        font-size: 0.9em;
        color: var(--secondary-text-color);
        line-height: 1;
      `;
      col1a.append(stateNameEl, friendlyEl);
      col1.append(iconEl, col1a);

      grid.appendChild(col1);

      // 3) display_attribute справа
      const col2 = document.createElement("div");
      col2.style.cssText = `
        display: flex;
        flex-direction: column;
        align-items: flex-end;
        flex: 0 0 1;
        font-size: 1.8em;
      `;

      const key = this._cfg.display_attribute;
      if (key) {
        // 1) создаём display-info как flex-контейнер
        const displayInfo = document.createElement("div");
        displayInfo.classList.add("display-info");

        // 2) пробуем получить имя иконки
        const iconName = this._computeAttributeIcon(key);
        // только если иконка есть — создаём и вставляем её
        if (iconName) {
          const iconEl = document.createElement("ha-icon");
          iconEl.icon = iconName;
          iconEl.style.cssText = `
            display: flex;
            --mdc-icon-size: 1.6em;
            flex: 0 0 1.6em;
          `;
          displayInfo.append(iconEl);
        }

        // 3) создаём текстовый контейнер
        const textWrapper = document.createElement("div");
        textWrapper.classList.add("display-info-text");
        textWrapper.style.cssText = `
          display: flex;
          flex-direction: column;
          gap: 4px;
        `;

        // 3a) текущее значение
        const value = this._hass.formatEntityAttributeValue(stateObj, key) || "–";
        const valueDiv = document.createElement("div");
        valueDiv.textContent = value;
        valueDiv.style.cssText = `
          display: inline-flex;
          line-height: 0.8;
          font-size: 0.9em;
          color: var(--text-color);
        `;
        textWrapper.append(valueDiv);

        // 3b) строка-placeholder с динамическим контентом
        // вычисляем текст для placeholder
        let placeholderText = "";
        const forecastType = this._cfg.forecast_type;
        // используем те же items, что и для графика:
        const items = arr.slice(0, this._cfg.forecast_slots ?? arr.length);
        const localeOptions = this.hass.locale || {};
        const fmtOpts = { minimumFractionDigits: 1, maximumFractionDigits: 1 };
        // достаём unit из атрибутов сущности
        const unitAttr = `${key}_unit`;
        const unit     = stateObj.attributes[unitAttr] || "";
        if (forecastType === "hourly") {
          // min/max за все hourly-слоты
          const vals = items.map(i => i[key]).filter(v => v != null);
          if (vals.length) {
            const mn = Math.min(...vals);
            const mx = Math.max(...vals);
            const mnFmt = this._formatNumberInternal(mn,  localeOptions, { minimumFractionDigits: 0, maximumFractionDigits: 1 });
            const mxFmt = this._formatNumberInternal(mx, localeOptions, { minimumFractionDigits: 0, maximumFractionDigits: 1 });
            // берём юнит один раз
            placeholderText = `${mnFmt}\u00A0/\u00A0${mxFmt}${unit ? `\u00A0${unit}` : ""}`;
          }
        } else {
          // daily или twice_daily: берём только первый элемент
          const first = items[0] || {};
          if (["temperature","temperature_low","temperature_high"].includes(key)) {
            // для температуры — templow и temperature
            const low  = first.templow ?? first.temperature  ?? 0;
            const high = first.temperature ?? low;
            const lowFormatted  = this._formatNumberInternal(low,  localeOptions, fmtOpts);
            const highFormatted = this._formatNumberInternal(high, localeOptions, fmtOpts) + "°";
            placeholderText = `${lowFormatted}\u00A0/\u00A0${highFormatted}${unit ? `\u00A0${unit}` : ""}`;
          } else if (first[key] != null) {
            // для любых других атрибутов — его значение
            placeholderText = `${first[key]}${unit ? `\u00A0${unit}` : ""}`;
          }
        }

        // создаём и добавляем placeholderDiv только если placeholderText непустой
        if (placeholderText) {
          const placeholderDiv = document.createElement("div");
          placeholderDiv.style.cssText = `
            display: inline-flex;
            line-height: 0.8;
            font-size: 0.5em;
            color: var(--secondary-text-color);
          `;
          placeholderDiv.textContent = placeholderText;
          textWrapper.appendChild(placeholderDiv);
        }

        // 4) собираем всё вместе
        displayInfo.append(textWrapper);

        // 5) вставляем в col3
        col2.appendChild(displayInfo);
      }

      grid.appendChild(col2);
      header.appendChild(grid);

      // 4) value_attribute — grid 2×4
      const valueGrid = document.createElement("div");
      valueGrid.style.cssText = `
        display: grid;
        width: 100%;
        grid-template-columns: 1fr auto;
        grid-template-rows: repeat(4, auto);
        align-items: center;
      `;
      for (let i = 1; i <= 8; i++) {
        const cfgKey = `value_attribute_${i}`;
        const attr = this._cfg[cfgKey];
        if (!attr) continue;
        const el = this._createAttributeValueEl(attr, stateObj);
        el.style.cssText += `color: var(--secondary-text-color);`;
        const col = i <= 4 ? 1 : 2;
        const row = i <= 4 ? i : i - 4;
        el.style.gridColumn = String(col);
        el.style.gridRow    = String(row);
        el.style.justifySelf  = 'start';
        el.style.whiteSpace = 'nowrap';
        valueGrid.appendChild(el);
      }
      header.appendChild(valueGrid);

      // Вставляем header
      this._body.appendChild(header);
      // Отдельный divider вместо border-bottom у header
      if (hasForecast && mode === "show_both") {
        const divider = document.createElement("div");
        divider.style.cssText = `
          width: 100%;
          border-bottom: 1px solid var(--divider-color);
          margin: 12px 0; /* отступ сверху/снизу */
        `;
        this._body.appendChild(divider);
      }
    }
  // --------------------
  // 2) ГРАФИЧЕСКИЙ БЛОК (прогноз)
  // --------------------
  if ((mode !== "show_current") && hasForecast) {
    // === Существующий блок с иконками ===
    if (["hourly", "twice_daily", "daily"].includes(this._cfg.forecast_type)
        && Array.isArray(arr) && arr.length) {
      const lang = this._hass.language || "en";
      const isSilamSource = stateObj.attributes.attribution === "Powered by silam.fmi.fi";
      const slots = this._cfg.forecast_slots ?? arr.length;
      const items = arr.slice(0, slots);
      

      const forecastIcons = {
        default: "mdi:flower-pollen-outline",
        state: {
          very_low:  "mdi:emoticon-happy-outline",
          low:       "mdi:emoticon-neutral-outline",
          moderate:  "mdi:emoticon-sad-outline",
          high:      "mdi:emoticon-cry-outline",
          very_high: "mdi:emoticon-dead-outline",
          unknown:   "mdi:progress-question"
        }
      };

      const chart = document.createElement("div");
      chart.style.cssText = `
        display: flex;
        gap: 8px;
        width: 100%;
        box-sizing: border-box;
        overflow-x: auto;
        -webkit-overflow-scrolling: touch;
      `;

      items.forEach(i => {
        const col = document.createElement("div");
        col.style.cssText = `
          display: flex;
          flex-direction: column;
          align-items: center;
          white-space: pre-wrap;
          overflow-wrap: break-word;
          flex: 1 1 0;
          width: 0;
          min-width: 36px;
          box-sizing: border-box;
        `;

        // Время / День / Ночь (с разделением шрифтов)
        const timeLabel = this._createTimeLabel(
          i,
          this._cfg.forecast_type,
          {
            // для основного блока шрифт 1em, вес 400
            timeFontSize: "1em",
            timeFontWeight: "400",
            // для hourly обычно без отступа; для остальных 2px
            timeMarginBottom: this._cfg.forecast_type === "hourly" ? "0" : "2px",
            // часть (Day/Night) чуть меньше
            partFontSize: "0.85em",
          }
        );
        col.appendChild(timeLabel);    

        // Иконка прогноза
        const iconName = isSilamSource
          ? (forecastIcons.state[i.condition] || forecastIcons.default)
          : null;
        if (iconName) {
          const iconEl = document.createElement("ha-icon");
          iconEl.icon = iconName;
          iconEl.style.cssText = `
            --mdc-icon-size: 2.2em;
            margin: 4px 0;
          `;
          col.appendChild(iconEl);
        } else {
          const iconEl = document.createElement("ha-state-icon");
          iconEl.hass     = this._hass;
          iconEl.stateObj = { entity_id: "weather.forecast", state: i.condition, attributes: {} };
          iconEl.style.cssText = `
            --mdc-icon-size: 2.2em;
            margin: 4px 0;
          `;
          col.appendChild(iconEl);
        }

        // Подпись ниже
        const labelEl = document.createElement("div");
        if (isSilamSource) {
          const condKey = `component.silam_pollen.entity.sensor.index.state.${i.condition}`;
          labelEl.textContent = this._t(condKey) || this._cond[i.condition] || i.condition;
          labelEl.style.cssText = `
            font-size: 0.75em;
            text-align: center;
            color: var(--secondary-text-color);
            line-height: 1.3;
            margin-top: 2px;
          `;
        } else {
          const temp = this._formatNumberInternal(
            i.temperature,
            this.hass.locale,
            { minimumFractionDigits: 1, maximumFractionDigits: 1 }
          );
          labelEl.textContent = `${temp}°`;
          labelEl.style.cssText = `
            font-size: 1.2em;
            text-align: center;
            margin-top: 2px;
          `;
        }
        col.appendChild(labelEl);
        // Для daily и twice_daily выводим ещё низшую температуру под основной
        if (!isSilamSource && ["daily", "twice_daily"].includes(this._cfg.forecast_type)) {
          const lowTemp = this._formatNumberInternal(
            i.templow,
            this.hass.locale,
            { minimumFractionDigits: 1, maximumFractionDigits: 1 }
          );
          const lowEl = document.createElement("div");          
          lowEl.textContent = `${lowTemp}°`;
          lowEl.style.cssText = `
            font-size: 1em;
            text-align: center;
            color: var(--secondary-text-color);
            margin-top: 2px;
          `;
          col.appendChild(lowEl);
        }

        chart.appendChild(col);
      });

      // Вставляем основной график (если не режим “только доп. блок”)
      if (!additionalOnly) {
        this._body.appendChild(chart);
        // И сразу под ним – divider, но только если есть дополнительный блок
        if (Array.isArray(this._cfg.additional_forecast) && this._cfg.additional_forecast.length) {
          const forecastDivider = document.createElement("div");
          forecastDivider.style.cssText = `
            width: 100%;
            border-bottom: 1px solid var(--divider-color);
            margin: 12px 0 4px; /* отступ сверху/снизу */
          `;
          this._body.appendChild(forecastDivider);
        }
      }

      // === Дополнительный блок: столбчатые графики по пыльце и другим атрибутам ===
      if (Array.isArray(this._cfg.additional_forecast) && this._cfg.additional_forecast.length) {
        const mode     = this._cfg.additional_forecast_mode || "standard";
        const stateObj = this._hass.states[this._cfg.entity];
        // Отбираем атрибуты, которые есть либо в атрибутах сущности, либо в первом элементе прогноза
        const availableAttrs = this._cfg.additional_forecast.filter(
          attr =>
            (stateObj.attributes[attr] != null) ||
            (Array.isArray(arr) && arr.length > 0 && arr[0][attr] != null)
        );
        if (!availableAttrs.length) {
          return;
        }

        // — режим «minimal»: только заголовки, без гистограмм —
        if (mode === "minimal") {
          const minimalRow = document.createElement("div");
          minimalRow.style.cssText = `
            display: flex;
            flex-wrap: wrap;
            gap: 16px;
            padding: 8px 0;
          `;
          availableAttrs.forEach(attr => {
            const pollenType = attr.replace("pollen_", "");
            const scale      = POLLEN_SCALES[pollenType];
            const currVal    = stateObj.attributes[attr] ?? 0;
            const iconName   = weatherAttrIcons[attr] || "mdi:flower-pollen";
            let iconColor    = "var(--primary-text-color)";
            if (scale) {
              let idx = scale.thresholds.findLastIndex(th => currVal >= th);
              if (idx < 0) idx = 0;
              iconColor = scale.colors[idx];
            }

            /* ---- контейнер header ---- */
            const hdr = document.createElement("div");
            hdr.style.cssText = `
              display: flex;
              flex-direction: column;
              align-items: center;
              width: 64px;
            `;

            /* ---- иконка ---- */
            const iconEl = document.createElement("ha-icon");
            iconEl.icon = iconName;
            iconEl.style.cssText = `
              --mdc-icon-size: 2.5em;
              color: ${iconColor};
              margin-bottom: 4px;
            `;
            hdr.appendChild(iconEl);

            /* ---- локализованное имя ---- */
            const nameEl = document.createElement("span");
            nameEl.textContent = this._hass.formatEntityAttributeName(stateObj, attr);
            nameEl.style.cssText = `
              font-size: 0.8em;
              text-align: center;
              margin-bottom: 4px;
            `;
            hdr.appendChild(nameEl);

            /* ---- значение ---- */
            const valEl = document.createElement("span");
            valEl.textContent = this._hass.formatEntityAttributeValue(stateObj, attr) || "–";
            valEl.style.cssText = `
              font-size: 0.9em;
              font-weight: 500;
            `;
            hdr.appendChild(valEl);

            minimalRow.appendChild(hdr);
          });
          this._body.appendChild(minimalRow);
          return;
        }

        // для стандартного и фокус-режима — строим привычный дополнительный блок
        const items = arr.slice(0, this._cfg.forecast_slots ?? arr.length);

        // — создаём общий обёрточный контейнер для всех sub-блоков —
        const wrapper = document.createElement("div");
        wrapper.style.cssText = `
          display: flex;
          gap: 1px;
          width: 100%;
          ${mode === "focus"
            ? `flex-direction: column;`
            : `flex-wrap: wrap; align-items: stretch;`
          }
        `;

        availableAttrs.forEach(attr => {
          const pollenType = attr.replace("pollen_", "");
          const scale      = POLLEN_SCALES[pollenType];
          const isTemp     = ["temperature", "temperature_low", "temperature_high"].includes(attr);

          /* -----------------------------------------------------------
            *  Контейнер для каждого блока до прогноза (пыльцы, температуры и т.д. header над гистограммами в focus)
            * --------------------------------------------------------- */
          // 0.1) сам block — это обёртка карточки для каждого атрибута
          const block = this._createBlockContainer(mode);
          // 0.2) wrapper с grid‐лейаутом (создаётся по режиму focus/standard)
          const includeTitle = !isTemp; // для температурных блоков заголовок не нужен
          const blockWrapper = this._createBlockWrapper(mode, includeTitle);
          // 0.3) titleContainer (опционально), отдаём в область «title»
          const titleContainer = this._createTitleContainer(mode);
          if (includeTitle) {
            titleContainer.style.gridArea = "title";
            blockWrapper.appendChild(titleContainer);
          }
          // 0.4) header: имя/иконка/значение — в область «header»
          const header = this._createHeaderContainer(mode);
          header.style.gridArea = "header";
          // 0.5) контейнер с графиком (bars или overlay) — в область «bars»
          const bars = document.createElement("div");
          bars.style.gridArea = "bars";
          
          // 0.6) собираем всё в блоке-wrapper
          blockWrapper.appendChild(header);
          blockWrapper.appendChild(bars);

          block.appendChild(blockWrapper);
          // 1) P O L L E N  (рендерим каждый аллерген: заголовок + иконка + мини-гистограмма)
          if (scale) {
            /* -----------------------------------------------------------
            *  1. Собираем текущее значение и прогнозные уровни
            * --------------------------------------------------------- */
            // текущее (базовое) значение пыльцы
            const baseVal = stateObj.attributes[attr] != null
              ? stateObj.attributes[attr]
              : 0;

            // прогнозные сырые уровни
            const rawLevels = [
              baseVal,
              ...items.map(i => (i[attr] != null ? i[attr] : 0))
            ];

            // пиковые уровни из прогноза
            const peakLevels = items.map(i =>
              i.allergen_peaks && i.allergen_peaks[pollenType]
                ? i.allergen_peaks[pollenType].peak
                : 0
            );

            // min/max по всему диапазону (текущее + прогноз + пики)
            const minLevel = Math.min(...rawLevels);
            const maxLevel = Math.max(...rawLevels, ...peakLevels);

            /* -----------------------------------------------------------
            *  2. Строим header: имя, иконка, значение, и контейнер min/max
            * --------------------------------------------------------- */
            // — создаём контейнер для базовой информации —
            const baseInfo = this._createSectionContainer(
              "base-info",
              mode,
              `
                ${mode === "focus"
                  ? ``
                  : `justify-content: space-between;`
                }
              `
            );            
            // имя аллергена
            const nameEl = document.createElement("span");
            nameEl.textContent = this._labels[attr] || pollenType;
            nameEl.style.cssText = `
              font-size: ${mode === "focus" ? "0.8em" : "1em"};
              font-weight: ${mode === "focus" ? "400" : "600"};
            `;
            titleContainer.appendChild(nameEl);

            // цвет иконки по текущему значению
            let iconIdx = scale.thresholds.findLastIndex(th => baseVal >= th);
            if (iconIdx < 0) iconIdx = 0;
            const iconColor = scale.colors[iconIdx];
            const icon = document.createElement("ha-icon");
            icon.icon = weatherAttrIcons[attr] || "mdi:flower-pollen";
            icon.style.cssText = `
              display: inline-flex;
              --mdc-icon-size: ${mode === "focus" ? "1.1em" : "3.0em"};
              color: ${iconColor};
              flex: ${mode === "focus" ? "0 0 1.1em" : "0 0 3.0em"};
            `;

            // 1) контейнер для всех значений и статистики
            const valueContainer = this._createValueContainer(mode);

            // 2) Первый flex-контейнер: текущее значение
            if (baseVal != null) {
              const currentEl = document.createElement("div");
              currentEl.textContent = this._hass.formatEntityAttributeValue(stateObj, attr);
              currentEl.style.cssText = `
                display: inline-flex;
                align-items: ${mode === "focus" ? "baseline" : "center"};
                line-height: 1;
                font-size: ${mode === "focus" ? "0.95em" : "1.6em"};
                font-weight: ${mode === "focus" ? "400" : "600"};
                ${mode === "focus"
                  ? `padding-right: 2px;`
                  : ``
                }
              `;
              valueContainer.appendChild(currentEl);
            }

            // 3) Второй flex-контейнер: min/max через слэш
            const minMaxEl = document.createElement("div");
            minMaxEl.style.cssText = `
              display: inline-flex;
              line-height: 1; 
              font-size: ${mode === "focus" ? "0.7em" : "1em"};
              color: var(--secondary-text-color);
              ${mode === "focus"
                ? `border-left: 1px solid var(--divider-color);
                  padding-left: 3px;`
                : ``
              }
            `;
            // предполагаем, что minLevel и maxLevel уже рассчитаны
            minMaxEl.textContent = `${minLevel} / ${maxLevel}`;
            valueContainer.appendChild(minMaxEl);

            // — добавляем все в baseInfo в нужном порядке—
            const baseElems = mode === "focus"
              ? [ icon, valueContainer ]
              : [ icon, valueContainer ];
            baseInfo.append(...baseElems);

            // — вешаем baseInfo в header —
            header.appendChild(baseInfo);

            /* -----------------------------------------------------------
             *  Контейнер мини-гистограммы (bars)
             * --------------------------------------------------------- */
            const bars = document.createElement("div");
            bars.style.cssText = `
              grid-area: bars;
              display: flex;
              align-items: flex-end;
              gap: clamp(1px, 2%, 10px);
              overflow-x: auto;
              overflow-y: visible;
              -webkit-overflow-scrolling: touch;
              flex: 1 1 auto;
              min-width: 0;
              box-sizing: border-box;
              padding-bottom: 4px;
            `;
            const segHeight = BAR_CHART_HEIGHT / POLLEN_SEGMENTS;

            /* -----------------------------------------------------------
             *  Предварительный расчёт числа sub-столбиков (colCount)
             * --------------------------------------------------------- */
            const colCount = (() => {
              switch (this._cfg.forecast_type) {
                case "hourly":      return 3;
                case "daily":       return 8;
                case "twice_daily": return 6;
                default:            return 1;
              }
            })();

            /* -----------------------------------------------------------
             *  Проход по каждой точке прогноза и формирование группы столбиков
             * --------------------------------------------------------- */
            const now = new Date();
            let nextPeakTime  = Infinity;
            let nextPeakValue = null;
            items.forEach(i => {
              // расчёт fillCount и цвета для основного столбца
              const concentration = i[attr] != null ? i[attr] : 0;
              let fillCount = 0;
              let color     = "transparent";
              if (concentration > 0) {
                let idx = scale.thresholds.findLastIndex(th => concentration >= th);
                if (idx < 0) idx = 0;
                fillCount = Math.min(idx + 1, POLLEN_SEGMENTS);
                color     = scale.colors[idx];
              }

              /* ---------------------------------------------------------
               *  Расчёт peakIndex и свой fillCount/color для текущего аллергена
               * ------------------------------------------------------- */
              let peakIndex     = null;
              let peakFillCount = 0;
              let peakColor     = "transparent";
              let peakTimeText  = "";
              let peakValue     = null;

              if (i.allergen_peaks && i.allergen_peaks[pollenType]) {
                const peakInfo = i.allergen_peaks[pollenType];
                const peakDt   = new Date(peakInfo.time);
                const peakVal  = peakInfo.peak;

                /* 1. длительность всего интервала */
                const intervalHours =
                  this._cfg.forecast_type === "hourly"      ? 1  :
                  this._cfg.forecast_type === "twice_daily" ? 12 : 24;

                /* 2. «реальное» начало окна */
                let intervalStart = new Date(i.datetime);

                if (this._cfg.forecast_type === "twice_daily") {
                  intervalStart = new Date(i.datetime);
                  if (i.is_daytime) {
                    intervalStart.setHours(6, 0, 0, 0);
                  } else {
                    intervalStart.setHours(18, 0, 0, 0);
                    if (peakDt < intervalStart) {
                      intervalStart.setDate(intervalStart.getDate() - 1);
                    }
                  }
                }

                /* 3. разница в часах от НАЧАЛА окна */
                const diffH = (peakDt - intervalStart) / 3_600_000;

                /* 4. индекс sub-столбца */
                const idx = Math.floor((diffH / intervalHours) * colCount);

                if (idx >= 0 && idx < colCount) {
                  peakIndex  = idx;
                  peakValue  = peakInfo.peak;

                  let pIdx = scale.thresholds.findLastIndex(th => peakValue >= th);
                  if (pIdx < 0) pIdx = 0;
                  peakFillCount = Math.min(pIdx + 1, POLLEN_SEGMENTS);
                  peakColor     = scale.colors[pIdx];
                  peakTimeText  = new Date(peakInfo.time)
                    .toLocaleTimeString(lang, withUserTimeZone(this.hass, { hour: "2-digit", minute: "2-digit" }));
                }
                  // ── запоминаем ближайший будущий пик, который строго > baseVal ──
                  if (peakDt > now
                    && peakVal > baseVal
                    && peakDt.getTime() < nextPeakTime) {
                  nextPeakTime  = peakDt.getTime();
                  nextPeakValue = peakVal;
                }
              }

              /* ---------------------------------------------------------
               *  Создание контейнера-группы для данного интервала
               * ------------------------------------------------------- */
              const group = document.createElement("div");
              group.style.cssText = `
                display: flex;
                flex-direction: column;
                align-items: center;
                flex: 1 1 0;
                min-width: ${colCount}px;
                box-sizing: border-box;
                position: relative;
              `;

              /* единый тултип для всего интервала */
              const tooltipText = peakIndex !== null
                ? `${concentration} (peak ${peakValue} @ ${peakTimeText})`
                : `${concentration}`;

              /* --- браузерный тултип для мыши --- */
              group.title = tooltipText;

              /* --- кастомный тултип для тач-экрана --- */
              group.addEventListener("pointerdown", (evt) => {
                if (evt.pointerType !== "touch") return;
                evt.stopPropagation();

                const tip = document.createElement("div");
                tip.textContent = tooltipText;
                tip.style.cssText = `
                  position: fixed;
                  left: ${evt.clientX}px;
                  top:  ${evt.clientY}px;
                  transform: translate(-50%, -120%);
                  background: var(--primary-background-color);
                  color: var(--primary-text-color);
                  padding: 3px 8px;
                  border-radius: 4px;
                  box-shadow: 0 2px 6px rgba(0,0,0,.35);
                  font-size: 0.75em;
                  white-space: nowrap;
                  pointer-events: none;
                  z-index: 2147483647;
                `;
                document.body.appendChild(tip);

                const removeTip = () => tip.remove();
                setTimeout(removeTip, 1500);
                document.addEventListener("pointerdown", removeTip, { once: true });
              });

              /* ---------------------------------------------------------
               *  Единая подпись (дата/время) для всей группы столбиков
               * ------------------------------------------------------- */
              const timeLabel = this._createTimeLabel(
                i,
                this._cfg.forecast_type,
                {
                  timeFontSize: "0.75em",
                  timeFontWeight: "400",
                  timeMarginBottom: "14px"
                }
              );
              group.appendChild(timeLabel);

              /* ---------------------------------------------------------
               *  Контейнер горизонтальных «термометрных» сегментов
               * ------------------------------------------------------- */
              const segContainer = document.createElement("div");
              segContainer.style.cssText = `
                display: flex;
                align-items: flex-end;
                width: 100%;
                height: ${BAR_CHART_HEIGHT}px;
                box-sizing: border-box;
                padding-top: 8px;
              `;

              /* ---------------------------------------------------------
               *  Отрисовка sub-столбиков, закраска пик-субстолбца особым цветом и тултип
               * ------------------------------------------------------- */
              for (let col = 0; col < colCount; col++) {
                const cell = document.createElement("div");
                cell.style.cssText = `
                  flex: 1 1 0;
                  width: 0;
                  display: flex;
                  flex-direction: column-reverse;
                  position: relative;
                  box-sizing: border-box;
                `;

                // для пика: используем свой fillCount/color и добавляем обработчик тача/клика
                const isPeakCol     = col === peakIndex;
                const thisFillCount = isPeakCol ? peakFillCount : fillCount;
                const thisColor     = isPeakCol ? peakColor     : color;

                for (let s = 0; s < POLLEN_SEGMENTS; s++) {
                  const filled = s < thisFillCount;               // закрашен ли сегмент

                  /* базовый стиль: фон + базовый «divider» */
                  let segCss = `
                    flex: 0 0 ${segHeight}px;
                    width: 100%;
                    background: ${filled ? thisColor : "transparent"};
                    border-top: 1px solid var(--divider-color);
                  `;

                  /* ── делаем пик темнее (≈ 80 % яркости) ── */
                  if (isPeakCol && filled) {
                    /* color-mix берёт 80 % исходного + 20 % black → на 20 % темнее */
                    const darker = `color-mix(in srgb, ${thisColor} 85%, black)`;
                  
                    segCss += `
                      /* слегка «утопим» сам фон */
                      background: ${darker};
                    `;
                  
                    /* добавим верхнюю линию только для последнего закрашенного сегмента */
                    if (s === thisFillCount - 1) {
                    }
                  }

                  const seg = document.createElement("div");
                  seg.style.cssText = segCss;
                  cell.appendChild(seg);
                }

                segContainer.appendChild(cell);
              }

              /* ---------------------------------------------------------
               *  Добавляем группу столбиков в общий контейнер bars
               * ------------------------------------------------------- */
              group.appendChild(segContainer);
              bars.appendChild(group);
            });

            // 4) После цикла: если нашли ближайший пик — оборачиваем в контейнер и добавляем в header
            if (nextPeakValue != null) {
              // вычисляем цвет для иконки по шкале
              const idx = scale.thresholds.findLastIndex(th => nextPeakValue >= th);
              const nextPeakColor = scale.colors[idx < 0 ? 0 : idx];

              // контейнер для блока «Peak»
              const peakContainer = this._createSectionContainer(
                "peak-info",
                mode,
                `
                  ${mode === "focus"
                    ? ``
                    : `justify-content: flex-end;`
                  }
                `
              );

              // 1) Иконка часов (цвет пика)
              const peakIcon = document.createElement("ha-icon");
              peakIcon.icon = "mdi:clock-alert-outline";
              peakIcon.style.cssText = `
                display: inline-flex;
                --mdc-icon-size: ${mode === "focus" ? "1.1em" : "2.0em"};
                color: ${nextPeakColor};
                flex: ${mode === "focus" ? "0 0 1.1em" : "0 0 2.0em"};
              `;

              // 2) Значение пика
              const valEl = document.createElement("div");
              valEl.textContent = `${nextPeakValue}`;
              valEl.style.cssText = `
                display: inline-flex;
                line-height: 1; 
                font-size: ${mode === "focus" ? "0.95em" : "1.2em"};
                font-weight: ${mode === "focus" ? "400" : "600"};
              `;

              // 3) День («сегодня», «завтра» или короткий weekday)
              const dt = new Date(nextPeakTime);
              const rawDay = this._formatRelativeDay(dt);
              const dayLabel = this._capitalize(rawDay);

              const dayEl = document.createElement("div");
              dayEl.textContent = dayLabel;
              dayEl.style.cssText = `
                display: inline-flex;
                line-height: 1; 
                font-size: ${mode === "focus" ? "0.7em" : "0.8em"};
                color: var(--secondary-text-color);
                ${mode === "focus"
                    ? 
                    `
                    padding-left: 3px;
                    border-left: 1px solid var(--divider-color);
                    `
                    : ``
                  }
              `;

              // 4) Время (локализованное, выделяем часы)
              const time = dt.toLocaleTimeString(this.hass.language, {
                hour:   "2-digit",
                minute: "2-digit",
              });
              const timeEl = document.createElement("div");
              timeEl.textContent = time;
              timeEl.style.cssText = `
                display: inline-flex;
                line-height: 1; 
                font-size: ${mode === "focus" ? "0.7em" : "0.8em"};
                color: var(--secondary-text-color);
                ${mode === "focus"
                    ? 
                    `
                    padding-left: 1px;
                    `
                    : ``
                  }
              `;
              // создаём wrapper значение\время
              const peakvalueContainer = this._createValueContainer(mode);
              peakvalueContainer.classList.add("peak-val-wrapper");

              peakvalueContainer.append(valEl, dayEl, timeEl);

              // — добавляем все в baseInfo в нужном порядке—
              const peakElems = mode === "focus"
                ? [ peakIcon, peakvalueContainer]
                : [ peakIcon, peakvalueContainer];
              peakContainer.append(...peakElems);
              // Добавляем готовый контейнер в header
              header.appendChild(peakContainer);
            }

            /* -----------------------------------------------------------
             *  Вставляем готовый блок пыльцы в DOM
             * --------------------------------------------------------- */
            blockWrapper.appendChild(bars);
          }


          // 2) TIME + TEMP FLEX OVERLAY + MIN/MAX/ZERO LINES
          else if (isTemp) {
            
            // берём ВСЕ templow (если есть) как кандидатов на минимум
            const highs = items.map(i => i[attr]).filter(v => v != null);
            const lows  = items.map(i => i.templow).filter(v => v != null);
            // tMin: если есть хоть одно templow — минимальный templow, иначе — минимальная temperature
            const tMin = lows.length
              ? Math.min(...lows)
              : Math.min(...highs);
            const tMax = Math.max(...highs);
            // флаг, что минимумы берём из templow
            const useLowExtremes = lows.length > 0;
            const range = tMax - tMin || 1;   // новый диапазон
            const chartH = 90;
            const markerH = 12;
            const labelMargin = 8; // отступ поверх/под маркером
            const offset = markerH / 2 + labelMargin;

            // базовая высота timeFlex
            const baseTFH = 30;          // px
            // если forecast_type == "twice_daily" → две строки → +40 %
            const tfh = this._cfg.forecast_type === "twice_daily"
              ? Math.round(baseTFH * 1.4)
              : baseTFH;
            const labelPadding  = 14;   // запас под подписи min/max/zero
            
            // — создаём контейнер для базовой информации —
            const baseInfo = this._createSectionContainer(
              "base-info",
              mode,
              `
                ${mode === "focus"
                  ? ``
                  : `justify-content: space-between;`
                }
              `
            );
            // — имя атрибута (например, «Температура») —
            //const nameEl = document.createElement("span");
            //nameEl.textContent = this.hass.formatEntityAttributeName(stateObj, attr);
            //nameEl.style.cssText = `
            //  font-size: ${mode === "focus" ? "0.8em" : "1em"};
            //  font-weight: ${mode === "focus" ? "400" : "600"};
            //  margin-bottom: ${mode === "focus" ? "0" : "4px"};
            //`;

            // — иконка термометра —
            const iconEl = document.createElement("ha-icon");
            iconEl.icon = "mdi:thermometer";
            iconEl.style.cssText = `
              display: inline-flex;
              --mdc-icon-size: ${mode === "focus" ? "1.1em" : "3.0em"};
              flex: ${mode === "focus" ? "0 0 1.1em" : "0 0 3.0em"};
            `;
            // 1) контейнер для всех значений и статистики
            const valueContainer = this._createValueContainer(mode);

            // Получаем опции локали (у вас могут быть в slightly другом поле)
            const localeOptions = this.hass.locale || {};
            // Аргументы для форматирования — одна дробная цифра
            const fmtOpts = { minimumFractionDigits: 1, maximumFractionDigits: 1 };
            // 2) Первый flex-контейнер: текущее значение
            if (stateObj.attributes[attr] != null) {
              const currentEl = document.createElement("div");
              const unitAttr = `${attr}_unit`;
              const unit     = stateObj.attributes[unitAttr] || "";
              currentEl.textContent = `${this._formatNumberInternal(stateObj.attributes[attr], localeOptions, fmtOpts)}${unit ? `\u00A0${unit}` : ""}`;
              currentEl.style.cssText = `
                display: inline-flex;
                align-items: ${mode === "focus" ? "baseline" : "center"};
                line-height: 1;
                font-size: ${mode === "focus" ? "0.95em" : "1.6em"};
                font-weight: ${mode === "focus" ? "400" : "600"};
                ${mode === "focus"
                  ? `padding-right: 2px;`
                  : ``
                }
              `;
              valueContainer.appendChild(currentEl);
            }

            // 3) Второй flex-контейнер: min/max через слэш
            const formattedMin = this._formatNumberInternal(tMin, localeOptions, fmtOpts);
            const formattedMax = this._formatNumberInternal(tMax, localeOptions, fmtOpts);
            const minMaxEl = document.createElement("div");
            minMaxEl.textContent = `${formattedMin}° / ${formattedMax}°`;
            minMaxEl.style.cssText = `
              display: inline-flex;
              line-height: 1; 
              font-size: ${mode === "focus" ? "0.7em" : "1em"};
              color: var(--secondary-text-color);
              ${mode === "focus"
                ? `border-left: 1px solid var(--divider-color);
                  padding-left: 3px;`
                : ``
              }
            `;
            valueContainer.appendChild(minMaxEl);

            // — добавляем все в baseInfo в нужном порядке—
            const baseElems = mode === "focus"
              ? [ iconEl, valueContainer ]
              : [ iconEl, valueContainer ];
            baseInfo.append(...baseElems);

            // — вешаем baseInfo в header —
            header.appendChild(baseInfo);

            /* -----------------------------------------------------------
             *  Оверлей: timeFlex + tempFlex + линии min/max/zero
             * --------------------------------------------------------- */
            
            const overlay = document.createElement("div");
            overlay.classList.add("hover-scroll");
            overlay.style.cssText = `
              position: relative;
              flex: 1 1 auto;
              min-width: 0;
              height: ${tfh + chartH + labelPadding}px;
              box-sizing: border-box;
            `;

            // 1) timeFlex с теми же стилями, что использовались раньше
            const timeFlex = document.createElement("div");
            timeFlex.style.cssText = `
              position:absolute; top:0; left:0; right:0;
              display:flex; align-items:flex-end;
              gap:clamp(1px,2%,10px);
              flex:1 1 auto; min-width:0; box-sizing:border-box;
              padding-bottom:4px; pointer-events:none;
            `;
            items.forEach((i) => {
              const cell = document.createElement("div");
              cell.style.cssText = `
                flex:1 1 0; min-width:16px; width:0;
                display:flex; flex-direction:column;
                align-items:center; text-align:center;
                color:var(--secondary-text-color);
                line-height:1;
              `;
              const timeLabel = this._createTimeLabel(
                i,
                this._cfg.forecast_type,
                {
                  timeFontSize: "0.75em",
                  timeFontWeight: "400",
                  timeMarginBottom: "2px"
                }
              );
              cell.appendChild(timeLabel);
              
              timeFlex.appendChild(cell);
            });
            overlay.appendChild(timeFlex);

            // 2) tempFlex
            const tempFlex = document.createElement("div");
            tempFlex.style.cssText = `
              position:absolute; top:${tfh}px; left:0; right:0;
              display:flex; align-items:flex-start;
              gap:clamp(1px,2%,10px);
              flex:1 1 auto; min-width:0; box-sizing:border-box;
              pointer-events:none;
            `;
            items.forEach((i) => {
              const vHigh = i[attr] != null ? i[attr] : tMin;
              const hasLow = i.templow != null;
              const vLow  = hasLow ? i.templow : vHigh;

              const normHigh = (vHigh - tMin) / range;
              const normLow  = (vLow  - tMin) / range;

              const offHigh = Math.round((1 - normHigh) * (chartH - markerH));
              const offLow  = Math.round((1 - normLow ) * (chartH - markerH));

              const centerHigh = offHigh + markerH / 2;
              const centerLow  = offLow  + markerH / 2;

              const barTop    = Math.min(centerHigh, centerLow);
              const barHeight = Math.abs(centerLow - centerHigh);

              // подсветка экстремумов
              const highlightMax = vHigh === tMax;
              const highlightMin = useLowExtremes
                ? (vLow === tMin)
                : (vHigh === tMin);

              const cell = document.createElement("div");
              cell.style.cssText = `
                position: relative;
                flex: 1 1 0;
                min-width: 16px;
                width: 0;
                height: ${chartH}px;
                box-sizing: border-box;
              `;

              const colorHigh = mapTempToColor(vHigh);
              const colorLow  = mapTempToColor(vLow);

              const bar = document.createElement("div");
              bar.style.cssText = `
                position: absolute;
                top: ${barTop}px;
                left: 50%;
                transform: translateX(-50%);
                width: clamp(60%,65%,70%);
                height: ${barHeight}px;
                background: linear-gradient(to bottom, ${colorHigh}, ${colorLow});
              `;
              cell.appendChild(bar);

              const markerHigh = document.createElement("div");
              markerHigh.style.cssText = `
                position: absolute;
                top: ${offHigh}px;
                left: 50%;
                transform: translateX(-50%);
                width: clamp(60%,65%,70%);
                height: ${markerH}px;
                background: ${colorHigh};
                border-radius: 3px;
              `;
              cell.appendChild(markerHigh);

              if (hasLow) {
                const markerLow = document.createElement("div");
                markerLow.style.cssText = `
                  position: absolute;
                  top: ${offLow}px;
                  left: 50%;
                  transform: translateX(-50%);
                  width: clamp(60%,65%,70%);
                  height: ${markerH}px;
                  background: ${colorLow};
                  border-radius: 3px;
                `;
                cell.appendChild(markerLow);
              }

              // рисуем lblHigh, учитывая и минимум для hourly
              const isExtremeHigh = highlightMax || (!hasLow && highlightMin);
              const lblHigh = document.createElement("div");
              lblHigh.textContent = `${this._formatNumberInternal(vHigh, localeOptions, fmtOpts)}°`;
              lblHigh.style.cssText = `
                position: absolute;
                top: ${centerHigh - offset}px;
                left: 50%;
                transform: translate(-50%, -50%);
                font-size: ${isExtremeHigh ? '0.95em' : '0.75em'};
                font-weight: ${isExtremeHigh ? '700'   : '400'};
                /* … остальные стили … */
              `;
              cell.appendChild(lblHigh);

              // рисуем lblLow, если есть templow
              if (hasLow) {
                const isExtremeLow = highlightMin;
                const lblLow = document.createElement("div");
                lblLow.textContent = `${this._formatNumberInternal(vLow, localeOptions, fmtOpts)}°`;
                lblLow.style.cssText = `
                  position: absolute;
                  top: ${centerLow + offset}px;
                  left: 50%;
                  transform: translate(-50%, -50%);
                  font-size: ${isExtremeLow ? '0.95em' : '0.75em'};
                  font-weight: ${isExtremeLow ? '700'   : '400'};
                  /* … остальные стили … */
                `;
                cell.appendChild(lblLow);
              }

              tempFlex.appendChild(cell);
            });
            overlay.appendChild(tempFlex);

            // 3) линии min/max и zero
            const maxLine = document.createElement("div");
            maxLine.style.cssText = `
              position:absolute;
              top:${tfh + markerH/2}px;
              left:0; right:0;
              border-top:1px solid var(--divider-color);
              pointer-events:none;
            `;
            overlay.appendChild(maxLine);

            const minLine = document.createElement("div");
            minLine.style.cssText = `
              position:absolute;
              top:${tfh + chartH - markerH/2}px;
              left:0; right:0;
              border-top:1px solid var(--divider-color);
              pointer-events:none;
            `;
            overlay.appendChild(minLine);

            if (tMin < 0 && tMax > 0) {
              const zeroNorm = (0 - tMin)/range;
              const zeroOff = Math.round((1 - zeroNorm)*(chartH - markerH));
              const zeroLine = document.createElement("div");
              zeroLine.style.cssText = `
                position:absolute;
                top:${tfh + zeroOff}px;
                left:0; right:0;
                border-top:1px dashed var(--divider-color);
                pointer-events:none;
              `;
              overlay.appendChild(zeroLine);
            }

            bars.appendChild(overlay);
          }



          // 3) TODO: добавить другие графики по другим атрибутам
          else {
            
            // — «подпись» атрибута (локализация или ключ) —
            const nameEl = document.createElement("span");
            nameEl.textContent = this._labels[attr] || attr;
            nameEl.style.cssText = `
              font-size: ${mode === "focus" ? "1.1em" : "1em"};
              font-weight: ${mode === "focus" ? "600" : "500"};
              margin-bottom: ${mode === "focus" ? "0" : "4px"};
            `;
            header.appendChild(nameEl);

            // — иконка для кастомного атрибута —
            const iconEl = document.createElement("ha-icon");
            iconEl.icon = weatherAttrIcons[attr] || "mdi:chart-bar";
            iconEl.style.cssText = `
              --mdc-icon-size: ${mode === "focus" ? "2em" : "3.5em"};
              margin-bottom: ${mode === "focus" ? "0" : "4px"};
            `;
            header.appendChild(iconEl);

            // — текстовое значение атрибута —
            const valEl = document.createElement("span");
            valEl.textContent = this._hass.formatEntityAttributeValue(stateObj, attr) || "–";
            valEl.style.cssText = `
              font-size: 0.9em;
            `;
            header.appendChild(valEl);

            // вставляем header в block
            block.appendChild(header);

            // — контейнер для пользовательского графика по attr —
            const custom = document.createElement("div");
            // TODO: тут реализовать отрисовку графика для данного атрибута
            block.appendChild(custom);
          }
          // — добавляем каждый block внутрь wrapper, а не сразу в this._body —
          wrapper.appendChild(block);
        });
      this._body.appendChild(wrapper);
      }


    }
  }
  // 3) Текстовый список прогноза — только если debug_forecast = true
  if (!this._cfg.debug_forecast) {
    return;
  }
  if (!Array.isArray(arr) || !arr.length) {
    // в режиме debug, но данных нет — можем вывести заглушку
    const msg = document.createElement("div");
    msg.style.cssText = "padding:8px;color:var(--secondary-text-color);";
    msg.textContent = this._t("no_forecast_data") || "No forecast data";
    this._body.appendChild(msg);
    return;
  }

  const lang = this._hass.language || "en";
  const ul = document.createElement("ul");
  ul.style.cssText = "list-style:none;padding:0;margin:0";
  ul.innerHTML = `
    <style>
      .pollen { color: var(--secondary-text-color); font-size: .9em }
      .pollen span { margin-right: 6px }
    </style>
    ${arr.map(i => this._rowHTML(i, lang)).join("")}
  `;
  this._body.appendChild(ul);
  }
                          
  _rowHTML(i,lang) {
    const dt   = new Date(i.datetime);
    const date = dt.toLocaleDateString(lang,withUserTimeZone(this.hass, {weekday:"short",month:"short",day:"numeric"}));
    const part = this._cfg.forecast_type==="twice_daily"
      ? (i.is_daytime===false
          ? this._hass.localize("ui.card.weather.night") || "Night"
          : this._hass.localize("ui.card.weather.day")   || "Day")
      : dt.toLocaleTimeString(lang,withUserTimeZone(this.hass, { hour: "2-digit", minute: "2-digit" }));
    const cond = this._cond[i.condition] || i.condition || "";

    const spans = [];
    i.pollen_index!=null &&
      spans.push(`<span>${this._indexLbl}: ${i.pollen_index}</span>`);
    for (const [k,lbl] of Object.entries(this._labels))
      i[k]!=null && spans.push(`<span>${lbl}: ${i[k]}</span>`);
    const pollen = spans.length ? `<div class="pollen">${spans.join(" ")}</div>` : "";

    return `<li style="margin:6px 0">
              <b>${date} ${part}</b> :
              ${i.temperature ?? "—"}° ${cond} ${pollen}
            </li>`;
  }
  /**
   * Правила размера карточки в секциях (sections view).
   * По умолчанию сетка делится на 12 колонок и ряды высотой 56px + 8px gap.
   * Здесь мы говорим: займём 2 ряда и 6 колонок, не меньше 1 ряда и не больше 3.
   */
  getGridOptions() {
    return {
      columns:    12,    // сколько колонок занять по-умолчанию (из 12)
      min_columns:   6,    // минимальное число рядов
    };
  }
  /* ====================================================================
   * required stubs
   * ==================================================================== */
  getCardSize() {
    return 4;
  }

  /**
   * При создании новой карточки из UI подставляем первую
   * подходящую weather-сущность silam_pollen_*_forecast
   */
  static getStubConfig(hass) {
    const ent = Object.keys(hass.states)
      .filter(id=> id.startsWith("weather.silam_pollen") && id.endsWith("_forecast"));
    return {
      type:           "custom:absolute-forecast-card",
      only_silam:     true,
      entity:         ent.length ? ent[0] : "",
      forecast_type:  "hourly",
      display_attribute: "",
    };
  }  

  /**
   * UI просит создать элемент-редактор
   */
  static getConfigElement() {
    return document.createElement("absolute-forecast-card-editor");
  }
}
customElements.define("absolute-forecast-card", AbsoluteForecastCard);

// ======================================================================
//  Visual editor для absolute-forecast-card
//  — показываем только weather.silam_pollen_*_forecast
// ======================================================================

class AbsoluteForecastCardEditor extends LitElement {
  static get properties() {
    return {
      _config: { type: Object },
      hass:    { type: Object },
      _helpers:{ type: Object },
    };
  }

  constructor() {
    super();
    this._config = {
      only_silam:     true, // по-умолчанию показываем только нашу интеграцию
      forecast:  "show_both",  // по умолчанию только прогноз
      additional_forecast: [],            // по умолчанию пусто
      additional_forecast_mode: "standard", // режим дополнительного блока
    };
    this._forecastSample = null; // атрибуты из первого пакета прогноза
    this._unsubForecast  = null; // функция-отписка от WS
  }

  setConfig(config) {
    this._config = {
      only_silam:        true,
      forecast:         "show_both",
      additional_forecast: [],
      additional_forecast_mode: "standard",
      ...config
    };
  }

  async firstUpdated() {
    // 1. Загружаем card helpers
    this._helpers = await window.loadCardHelpers();

    // 2. Подгружаем переводы для текущей entity (если задана)
    if (this._config.entity) {
      await this._loadTranslationsForEntity(this._config.entity);
      await this._setupForecastSubscription();
    }
  }

  // все weather.silam_pollen_*_forecast
  _getSilamEntities() {
    return Object.keys(this.hass.states)
      .filter(eid =>
        eid.startsWith("weather.silam_pollen") &&
        eid.endsWith("_forecast")
      )
      .sort();
  }

  async _valueChanged(ev) {
    const cfg = { ...this._config, ...ev.detail.value };
    const entityChanged       = cfg.entity        !== this._config.entity;
    const forecastTypeChanged = cfg.forecast_type !== this._config.forecast_type;
    this._config = cfg;

    // При смене entity — перезагрузим переводы
    if (cfg.entity) {
      await this._loadTranslationsForEntity(cfg.entity);
    }
    if (entityChanged || forecastTypeChanged) {
      await this._setupForecastSubscription();
    }

    this.dispatchEvent(new CustomEvent("config-changed", {
      detail: { config: cfg },
      bubbles: true,
      composed: true,
    }));
  }

  _computeLabelCallback = (schema) => {
    if (!this.hass) return;

    switch (schema.name) {
      // Обязательное поле
      case "entity":
        return `${this.hass.localize("ui.panel.lovelace.editor.card.generic.entity")} ` +
              `(${this.hass.localize("ui.panel.lovelace.editor.card.config.required")})`;

      // То же для forecast_type и forecast_slots
      case "forecast_type":
        return this.hass.localize(
          "ui.panel.lovelace.editor.card.weather-forecast.forecast_type"
        );
      case "forecast_slots":
        return this.hass.localize(
          "ui.panel.lovelace.editor.card.weather-forecast.forecast_slots"
        );
      case "forecast":
        return this.hass.localize(
          "ui.panel.lovelace.editor.card.weather-forecast.weather_to_show"
        );

      // Поле "name"
      case "name":
        return this.hass.localize(
          "ui.panel.lovelace.editor.card.generic.name"
        );

      // Фоллбек — generic для любого другого поля
      default:
        return this.hass.localize(
          `ui.panel.lovelace.editor.card.generic.${schema.name}`
        ) || schema.label || schema.name;
    }
  };

  /**
   * Определяем через entityRegistry, к какой интеграции принадлежит entity,
   * и загружаем её переводы из backend
   */
  async _loadTranslationsForEntity(entityId) {
    if (!this.hass || !this._helpers) return;
  
    try {
      const entry = await this._helpers.entityRegistry.getEntityRegistryEntry(entityId);
      if (entry?.platform) {
        await this.hass.loadBackendTranslation(entry.platform, this.hass.language);
      }
    } catch (err) {
      console.warn("Translation load failed:", err);
    }
  }

  async _setupForecastSubscription() {
    // 1) убрать прежнюю подписку, если была
    if (this._unsubForecast) {
      this._unsubForecast();
      this._unsubForecast = null;
    }
  
    const { entity } = this._config;
    if (!this.hass || !entity) return;
    
    // ── выбираем forecast_type динамически ─────────────────────────────
    const stateObj = this.hass.states[entity];
    let  type = this._config.forecast_type;           // то, что уже выбрано
    if (!type) {
      // первый доступный: hourly → daily → twice_daily
      if (forecastSupported(stateObj, "hourly"))       type = "hourly";
      else if (forecastSupported(stateObj, "daily"))   type = "daily";
      else if (forecastSupported(stateObj, "twice_daily")) type = "twice_daily";
      else                                            type = "hourly";  // fallback
      this._config.forecast_type = type;              // сохраняем в конфиг
    }
     // ───────────────────────────────────────────────────────────────────
    
  
    // 2) подписываемся напрямую через WebSocket
    this._unsubForecast = await this.hass.connection.subscribeMessage(
      (msg) => {
        if (Array.isArray(msg.forecast) && msg.forecast.length) {
          this._forecastSample = msg.forecast[0]; // сохранили ключи
          this.requestUpdate();                   // перерисуем меню
        }
      },
      {
        type: "weather/subscribe_forecast",
        entity_id: entity,
        forecast_type: type,
      },
    );
  }  

  _combineAttributeOptions(entityId) {
    const stateObj = this.hass.states[entityId];
    if (!stateObj || !stateObj.attributes) {
      return [];
    }
    const weatherProps = [
      "cloud_coverage",
      "humidity",
      "apparent_temperature",
      "dew_point",
      "pressure",
      "temperature",
      "visibility",
      "wind_gust_speed",
      "wind_speed",
      "ozone",
      "uv_index",
      "wind_bearing",
      "precipitation_probability",
      "precipitation",
    ];
    const seen = new Set();
    const baseKeys     = Object.keys(stateObj.attributes);
    const forecastKeys = this._forecastSample ? Object.keys(this._forecastSample) : [];
    const allKeys      = [...new Set([...baseKeys, ...forecastKeys])];

    return allKeys
      .filter(
        (attr) =>
          weatherProps.includes(attr) ||      // любой из списка выше
          attr.startsWith("pollen_")          // или любой pollen_*
      )
      .map((a) => {
        if (seen.has(a)) return null;
        seen.add(a);
        return {
          value: a,
          label: this.hass.formatEntityAttributeName(stateObj, a),  // ← всё готово
        };
      })
      .filter(Boolean);
  }

  render() {
    if (!this._helpers || !this.hass) return html``;

    const silam = this._config.only_silam !== false;
    const silamEntities = silam ? this._getSilamEntities() : [];

        // ---------- динамический forecast_type ----------
    const stateObj = this.hass.states[this._config.entity];
    let forecastTypeOptions = [];

    if (forecastSupported(stateObj, "hourly")) {
      forecastTypeOptions.push({
        value: "hourly",
        label: this.hass.localize("ui.panel.lovelace.editor.card.weather-forecast.hourly"),
      });
    }
    if (forecastSupported(stateObj, "daily")) {
      forecastTypeOptions.push({
        value: "daily",
        label: this.hass.localize("ui.panel.lovelace.editor.card.weather-forecast.daily"),
      });
    }
    if (forecastSupported(stateObj, "twice_daily")) {
      forecastTypeOptions.push({
        value: "twice_daily",
        label: this.hass.localize("ui.panel.lovelace.editor.card.weather-forecast.twice_daily"),
      });
    }

    // если сущность не сообщает supported_features ― покажем все варианты
    if (!forecastTypeOptions.length) {
      forecastTypeOptions = [
        { value: "hourly",      label: this.hass.localize("ui.panel.lovelace.editor.card.weather-forecast.hourly") },
        { value: "daily",       label: this.hass.localize("ui.panel.lovelace.editor.card.weather-forecast.daily") },
        { value: "twice_daily", label: this.hass.localize("ui.panel.lovelace.editor.card.weather-forecast.twice_daily") },
      ];
    }

    const options = this._combineAttributeOptions(this._config.entity);
    
    // 1) базовые поля
    const baseSchema = [
      {
        name: "only_silam",
        selector: { boolean: {} },
        default: true,
      },
      {
        name: "entity",
        required: true,
        selector: {
          entity: silam
            ? { include_entities: silamEntities }
            : { domain: "weather" },
        },
      },
      {
        name: "display_attribute",
        selector: { attribute: {} },
        context: { filter_entity: "entity" },
      },
    ];

    // 2) ваши 4 грида
    const advancedSchema = [
      {
        name: "",
        type: "grid",
        schema: [
          { name: "value_attribute_1",   selector: { attribute: {} }, context: { filter_entity: "entity" } },
          { name: "value_attribute_5", selector: { attribute: {} }, context: { filter_entity: "entity" } },
        ],
      },
      {
        name: "",
        type: "grid",
        schema: [
          { name: "value_attribute_2", selector: { attribute: {} }, context: { filter_entity: "entity" } },
          { name: "value_attribute_6", selector: { attribute: {} }, context: { filter_entity: "entity" } },
        ],
      },
      {
        name: "",
        type: "grid",
        schema: [
          { name: "value_attribute_3", selector: { attribute: {} }, context: { filter_entity: "entity" } },
          { name: "value_attribute_7", selector: { attribute: {} }, context: { filter_entity: "entity" } },
        ],
      },
      {
        name: "",
        type: "grid",
        schema: [
          { name: "value_attribute_4", selector: { attribute: {} }, context: { filter_entity: "entity" } },
          { name: "value_attribute_8", selector: { attribute: {} }, context: { filter_entity: "entity" } },
        ],
      },
    ];

    // 3) итоговая схема с expandable
    const schema = [
      ...baseSchema,
      {
        name:     "content",
        type:     "expandable",
        iconPath: "mdi:text-short",
        flatten:  true,
        schema:   advancedSchema,
      },
      {
        name: "forecast",
        selector: {
          select: {
            options: [
              { value: "show_current",  label: this.hass.localize("ui.panel.lovelace.editor.card.weather-forecast.show_only_current")},
              { value: "show_forecast", label: this.hass.localize("ui.panel.lovelace.editor.card.weather-forecast.show_only_forecast")},
              { value: "show_both",     label: this.hass.localize("ui.panel.lovelace.editor.card.weather-forecast.show_both")},
            ]
          }
        },
        default: this._config.forecast,
      },
      {
        name: "forecast_type",
        selector: {
          select: { options: forecastTypeOptions },
        },
      },      
      {
        name: "forecast_slots",
        selector: { number: { min: 1, max: 12 } },
        default: this._config.forecast_slots ?? 5,
      },      
      {
        name: "additional_only",
        label: "Показывать только дополнительный блок",
        selector: { boolean: {} },
        default: this._config.additional_only,
      },
      {
        name: "additional_forecast",
        selector: {
          select: {
            reorder: true,        // разрешить менять порядок
            multiple: true,
            custom_value: true,   // позволить вводить свои значения
            options               // ваши варианты из переменной options
          }
        },
        default: this._config.additional_forecast
      },
      // Новый параметр: режим дополнительного блока
      {
        name: "additional_forecast_mode",
        label: "Режим дополнительного блока",
        selector: {
          select: {
            options: [
              { value: "standard", label: "Стандартный" },
              { value: "focus",    label: "Фокусировка" },
              { value: "minimal",  label: "Минимальный" },
            ]
          }
        },
        default: this._config.additional_forecast_mode,
      },
      {
        name: "debug_forecast",
        label: this.hass.localize("component.silam_pollen.editor.debug_forecast"),
        selector: { boolean: {} },
        default: false,
      },
    ];

    return html`
      <div style="padding:16px">
        <ha-form
          .hass=${this.hass}
          .data=${this._config}
          .schema=${schema}
          .computeLabel=${this._computeLabelCallback}
          @value-changed=${this._valueChanged}
        ></ha-form>
      </div>
    `;
  }
}

customElements.define(
  "absolute-forecast-card-editor",
  AbsoluteForecastCardEditor
);

// ======================================================================
//  Регистрируем карточку в списке Custom Cards
// ======================================================================
window.customCards = window.customCards || [];
window.customCards.push({
  type: "absolute-forecast-card",
  name: "Absolute Forecast Card",
  description: "Absolute forecast card (uses native weather selector)"
});