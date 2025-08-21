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
  apparent_temperature:      "mdi:thermometer-lines",
  cloud_coverage:            "mdi:cloud-percent-outline",
  dew_point:                 "mdi:water-thermometer-outline",
  humidity:                  "mdi:water-percent",
  wind_bearing:              "mdi:compass-rose",
  wind_speed:                "mdi:weather-windy",
  pressure:                  "mdi:gauge",
  temperature:               "mdi:thermometer",
  uv_index:                  "mdi:sun-wireless",
  visibility:                "mdi:eye-outline",
  precipitation:             "mdi:weather-rainy",
  precipitation_probability: "mdi:weather-rainy",

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

// ---- наборы состояний из weather.ts ----
const weatherSVGs = new Set([
  "clear-night","cloudy","fog","lightning","lightning-rainy",
  "partlycloudy","pouring","rainy","hail","snowy","snowy-rainy",
  "sunny","windy","windy-variant",
]);

const cloudyStates    = new Set(["partlycloudy","cloudy","fog","windy","windy-variant","hail","rainy","snowy","snowy-rainy","pouring","lightning","lightning-rainy"]);
const rainStates      = new Set(["hail","rainy","pouring","lightning-rainy"]);
const windyStates     = new Set(["windy","windy-variant"]);
const snowyStates     = new Set(["snowy","snowy-rainy"]);
const lightningStates = new Set(["lightning","lightning-rainy"]);


/**
 * Безопасно добавляет SVG-пути в элемент svgEl.
 * @param {SVGSVGElement} svgEl
 * @param {Array<{d: string, class?: string}>} paths
 */
function addPathsSafe(svgEl, paths) {
  const SVG_NS = "http://www.w3.org/2000/svg";
  paths.forEach(({ d, class: cls }) => {
    const pathEl = document.createElementNS(SVG_NS, "path");
    pathEl.setAttribute("d", d);
    if (cls) pathEl.setAttribute("class", cls);
    svgEl.appendChild(pathEl);
  });
}

/**
 * Возвращает SVG для состояния погоды.
 * @param {string} state
 * @param {boolean} nightTime
 * @returns {SVGSVGElement}
 */
function getWeatherStateSVG(state, nightTime = false) {
  const SVG_NS = "http://www.w3.org/2000/svg";
  // Если нет такого состояния — вернём пустой <svg>
  if (!weatherSVGs.has(state)) {
    return document.createElementNS(SVG_NS, "svg");
  }
  // Создаём корневой <svg>
  const svgEl = document.createElementNS(SVG_NS, "svg");
  svgEl.setAttribute("viewBox", "0 0 17 17");
  svgEl.classList.add("forecast-image-icon");
  // Дальше просто используем глобальные множества:
  // Состояние «солнечно»
  if (state === "sunny") {
    addPathsSafe(svgEl, [
      {
        class: "sun",
        d: "m14.39303,8.4033507 c0,3.3114723-2.684145,5.9956173-5.9956169,5.9956173-3.3114716,0-5.9956168-2.684145-5.9956168-5.9956173 0-3.311471 2.6841452-5.995617 5.9956168-5.995617 3.3114719,0 5.9956169,2.684146 5.9956169,5.995617"
      }
    ]);
  }

  // Состояние «ясная ночь»
  if (state === "clear-night") {
    addPathsSafe(svgEl, [
      {
        class: "moon",
        d: "m13.502891,11.382935 c-1.011285,1.859223-2.976664,3.121381-5.2405751,3.121381-3.289929,0-5.953329-2.663833-5.953329-5.9537625 0-2.263911 1.261724-4.228856 3.120948-5.240575-0.452782,0.842738-0.712753,1.806363-0.712753,2.832381 0,3.289928 2.663833,5.9533275 5.9533291,5.9533275 1.026017,0 1.989641-0.259969 2.83238-0.712752"
      }
    ]);
  }
  if (state === "partlycloudy") {
    // Выбираем нужный путь в зависимости от ночи
    const d = nightTime
      ? "m14.981 4.2112c0 1.9244-1.56 3.4844-3.484 3.4844-1.9244 0-3.4844-1.56-3.4844-3.4844s1.56-3.484 3.4844-3.484c1.924 0 3.484 1.5596 3.484 3.484"
      : "m14.981 4.2112c0 1.9244-1.56 3.4844-3.484 3.4844-1.9244 0-3.4844-1.56-3.4844-3.4844s1.56-3.484 3.4844-3.484c1.924 0 3.484 1.5596 3.484 3.484";
  
    addPathsSafe(svgEl, [
      {
        class: nightTime ? "moon" : "sun",
        d,
      }
    ]);
  }
  // 3) Облачно: задний и передний облака
  if (cloudyStates.has(state)) {
    addPathsSafe(svgEl, [
      {
        class: "cloud-back",
        d: "m3.8863 5.035c-0.54892 0.16898-1.04 0.46637-1.4372 0.8636-0.63077 0.63041-1.0206 1.4933-1.0206 2.455 0 1.9251 1.5589 3.4682 3.4837 3.4682h6.9688c1.9251 0 3.484-1.5981 3.484-3.5232 0-1.9251-1.5589-3.5232-3.484-3.5232h-1.0834c-0.25294-1.6916-1.6986-2.9083-3.4463-2.9083-1.7995 0-3.2805 1.4153-3.465 3.1679"
      },
      {
        class: "cloud-front",
        d: "m4.1996 7.6995c-0.33902 0.10407-0.64276 0.28787-0.88794 0.5334-0.39017 0.38982-0.63147 0.92322-0.63147 1.5176 0 1.1896 0.96414 2.1431 2.1537 2.1431h4.3071c1.1896 0 2.153-0.98742 2.153-2.1777 0-1.1896-0.96344-2.1777-2.153-2.1777h-0.66992c-0.15593-1.0449-1.0499-1.7974-2.1297-1.7974-1.112 0-2.0274 0.87524-2.1417 1.9586"
      }
    ]);
  }
  // дождь, град и «lightning-rainy»
  if (rainStates.has(state)) {
    addPathsSafe(svgEl, [
      {
        class: "rain",
        d: "m5.2852 14.734c-0.22401 0.24765-0.57115 0.2988-0.77505 0.11395-0.20391-0.1845-0.18732-0.53481 0.036689-0.78281 0.14817-0.16298 0.59126-0.32914 0.87559-0.42369 0.12453-0.04092 0.22684 0.05186 0.19791 0.17956-0.065617 0.2921-0.18732 0.74965-0.33514 0.91299"
      },
      {
        class: "rain",
        d: "m11.257 14.163c-0.22437 0.24765-0.57115 0.2988-0.77505 0.11395-0.2039-0.1845-0.18768-0.53481 0.03669-0.78281 0.14817-0.16298 0.59126-0.32914 0.8756-0.42369 0.12453-0.04092 0.22684 0.05186 0.19791 0.17956-0.06562 0.2921-0.18732 0.74965-0.33514 0.91299"
      },
      {
        class: "rain",
        d: "m8.432 15.878c-0.15452 0.17039-0.3937 0.20567-0.53446 0.07867-0.14041-0.12735-0.12876-0.36865 0.025753-0.53975 0.10195-0.11218 0.40711-0.22684 0.60325-0.29175 0.085725-0.02858 0.15628 0.03563 0.13652 0.12382-0.045508 0.20108-0.12912 0.51647-0.23107 0.629"
      },
      {
        class: "rain",
        d: "m7.9991 14.118c-0.19226 0.21237-0.49001 0.25612-0.66499 0.09737-0.17462-0.15804-0.16051-0.45861 0.03175-0.67098 0.12665-0.14005 0.50729-0.28293 0.75071-0.36336 0.10689-0.03563 0.19473 0.0441 0.17004 0.15346-0.056092 0.25082-0.16051 0.64347-0.28751 0.78352"
      }
    ]);
  }
  // проливной дождь
  if (state === "pouring") {
    addPathsSafe(svgEl, [
      {
        class: "rain",
        d: "m10.648 16.448c-0.19226 0.21449-0.49001 0.25894-0.66499 0.09878-0.17498-0.16016-0.16087-0.4639 0.03175-0.67874 0.12665-0.14146 0.50694-0.2854 0.75071-0.36724 0.10689-0.03563 0.19473 0.0448 0.17004 0.15558-0.05645 0.25365-0.16051 0.65017-0.28751 0.79163"
      },
      {
        class: "rain",
        d: "m5.9383 16.658c-0.22437 0.25012-0.5715 0.30162-0.77505 0.11501-0.20391-0.18627-0.18768-0.54046 0.036689-0.79093 0.14817-0.1651 0.59126-0.33267 0.87559-0.42827 0.12418-0.04127 0.22648 0.05221 0.19791 0.18168-0.065617 0.29528-0.18732 0.75741-0.33514 0.92251"
      }
    ]);
  }
  if (windyStates.has(state)) {
    addPathsSafe(svgEl, [
      {
        class: "cloud-back",
        d: "m13.59616,15.30968c0,0-0.09137-0.0071-0.250472-0.0187-0.158045-0.01235-0.381353-0.02893-0.64382-0.05715-0.262466-0.02716-0.564444-0.06385-0.877358-0.124531-0.156986-0.03034-0.315383-0.06844-0.473781-0.111478-0.157691-0.04551-0.313266-0.09842-0.463902-0.161219l-0.267406-0.0949c-0.09984-0.02646-0.205669-0.04904-0.305153-0.06738-0.193322-0.02716-0.3838218-0.03316-0.5640912-0.02011-0.3626556,0.02611-0.6847417,0.119239-0.94615,0.226483-0.2617611,0.108656-0.4642556,0.230364-0.600075,0.324203-0.1358195,0.09419-0.2049639,0.160514-0.2049639,0.160514 0,0 0.089958-0.01623 0.24765-0.04445 0.1559278-0.02575 0.3764139-0.06174 0.6367639-0.08714 0.2596444-0.02646 0.5591527-0.0441 0.8678333-0.02328 0.076905,0.0035 0.1538111,0.01658 0.2321278,0.02293 0.077611,0.01058 0.1534581,0.02893 0.2314221,0.04022 0.07267,0.01834 0.1397,0.03986 0.213078,0.05644l0.238125,0.08925c0.09207,0.03281 0.183444,0.07055 0.275872,0.09878 0.09243,0.0261 0.185208,0.05327 0.277636,0.07161 0.184856,0.0388 0.367947,0.06174 0.543983,0.0702 0.353131,0.01905 0.678745-0.01341 0.951442-0.06456 0.27305-0.05292 0.494595-0.123119 0.646642-0.181681 0.152047-0.05785 0.234597-0.104069 0.234597-0.104069"
      },
      {
        class: "cloud-back",
        d: "m4.7519154,13.905801c0,0 0.091369-0.0032 0.2511778-0.0092 0.1580444-0.0064 0.3820583-0.01446 0.6455833-0.03281 0.2631722-0.01729 0.5662083-0.04269 0.8812389-0.09137 0.1576916-0.02434 0.3175-0.05609 0.4776611-0.09384 0.1591027-0.03951 0.3167944-0.08643 0.4699-0.14358l0.2702277-0.08467c0.1008945-0.02222 0.2074334-0.04127 0.3072695-0.05574 0.1943805-0.01976 0.3848805-0.0187 0.5651499,0.0014 0.3608917,0.03951 0.67945,0.144639 0.936625,0.261761 0.2575278,0.118534 0.4554364,0.247297 0.5873754,0.346781 0.132291,0.09913 0.198966,0.168275 0.198966,0.168275 0,0 -0.08925-0.01976 -0.245886-0.05397c-0.1786755,0.042175-0.39775,0. -0.65804019-0.03441-0.88744995?,14.087088 9.7232597,14.042988 9.4639681,14.00736 9.2057347,13.97173 8.9072848,13.94245 8.5978986,13.95162c-0.077258,7.06e-4-0.1541638,0.01058-0.2328333,0.01411-0.077964,0.0078-0.1545166,0.02328-0.2331861,0.03175-0.073025,0.01588-0.1404055,0.03422-0.2141361,0.04798l-0.2420055,0.08008c-0.093486,0.02963-0.1859139,0.06421-0.2794,0.0889c-0.1851747,0.05147-0.278661,0.07511-0.4075326b,0.09507?"
      }
    ]);
  }
  // снег и «snowy-rainy»
  if (snowyStates.has(state)) {
    addPathsSafe(svgEl, [
      {
        class: "snow",
        d: "m8.4319893,15.348341c0,0.257881-0.209197,0.467079-0.467078,0.467079-0.258586,0-0.46743-0.209198-0.46743-0.467079 0-0.258233 0.208844-0.467431 0.46743-0.467431 0.257881,0 0.467078,0.209198 0.467078,0.467431"
      },
      {
        class: "snow",
        d: "m11.263878,14.358553c0,0.364067-0.295275,0.659694-0.659695,0.659694-0.364419,0-0.6596937-0.295627-0.6596937-0.659694 0-0.364419 0.2952747-0.659694 0.6596937-0.659694 0.36442,0 0.659695,0.295275 0.659695,0.659694"
      },
      {
        class: "snow",
        d: "m5.3252173,13.69847c0,0.364419-0.295275,0.660047-0.659695,0.660047-0.364067,0-0.659694-0.295628-0.659694-0.660047 0-0.364067 0.295627-0.659694 0.659694-0.659694 0.36442,0 0.659695,0.295627 0.659695,0.659694"
      }
    ]);
  }
  // молния и «lightning-rainy»
  if (lightningStates.has(state)) {
    addPathsSafe(svgEl, [
      {
        class: "sun",
        d: "m9.9252695,10.935875-1.6483986,2.341014 1.1170184,0.05929-1.2169864,2.02141 3.0450261,-2.616159H9.8864918L10.97937,11.294651 10.700323,10.79794h-0.508706l-0.2663475,0.137936"
      }
    ]);
  }

  return svgEl;
}

/* -----------------------------------------------------------------
 * 1. Таблицы порогов (мм/12 ч)
 * https://www.primgidromet.ru/weather/terminy-primenyaemye-v-prognozah/
 * ---------------------------------------------------------------- */
const RAIN_THRESH = [0.05, 2, 14, 49, 1e9];  // пять точек → 0-4 уровни
const SNOW_THRESH = [0.05, 1, 6, 19, 1e9];

/* Возвращает уровень 0-4 */
function precipLevel(amount, slotHours, isSnow) {
  const scale = slotHours / 12;                 // перевод к 12-ч эквиваленту
  const th    = isSnow ? SNOW_THRESH : RAIN_THRESH;
  let lvl = 0;
  while (lvl < 4 && amount >= th[lvl] * scale) lvl++;
  return lvl;           // 0-4
}

// Общие атрибуты для всех мини-SVG (не обрезать и немного расширить ширину)
const SHARED_SVG_ATTRS = `viewBox="0 0 24 24" style="overflow:visible; width:120%"`;

/* ---------- «естественная» капля ----------
   Слои:
   - нижний: мягкая обводка (подложка), чтобы не терялась на белом
   - верхний: заливка currentColor
   - блики: два светлых штриха (боковой и нижний полублик)
*/
const dropGroup = `
  <g>
    <!-- подложка-контур -->
    <path d="M12 3
             C 9.4 7.1, 7.8 9.6, 7.6 12.7
             a 4.6 4.6 0 0 0 9.2 0
             c 0-3.1-1.5-5.7-4.8-9.7 Z"
          fill="none" stroke="rgba(0,0,0,.28)" stroke-width="1.2"/>

    <!-- заливка капли -->
    <path d="M12 3
             C 9.4 7.1, 7.8 9.6, 7.6 12.7
             a 4.6 4.6 0 0 0 9.2 0
             c 0-3.1-1.5-5.7-4.8-9.7 Z"
          fill="currentColor"/>

    <!-- мягкий боковой блик -->
    <path d="M10.1 9.8
             C 11.0 8.2, 12.2 6.5, 13.3 5.2"
          fill="none" stroke="#fff" stroke-opacity=".35"
          stroke-width=".6" stroke-linecap="round"/>

    <!-- нижний полублик -->
    <path d="M9.4 14.4
             c 1.0 1.8, 4.2 1.8, 5.2 0"
          fill="none" stroke="#fff" stroke-opacity=".22"
          stroke-width=".75" stroke-linecap="round"/>
  </g>
`;

/* ---------- 0 … 4 «капли» (дождь) — с аккуратной раскладкой ---------- */
const rainSVG = [
  /* 0 — пустое */
  `<svg xmlns="http://www.w3.org/2000/svg" ${SHARED_SVG_ATTRS}></svg>`,

  /* 1 — одна капля по центру */
  `<svg xmlns="http://www.w3.org/2000/svg" ${SHARED_SVG_ATTRS}>
     ${dropGroup}
   </svg>`,

  /* 2 — две капли (чуть меньше, разнесены и слегка повернуты) */
  `<svg xmlns="http://www.w3.org/2000/svg" ${SHARED_SVG_ATTRS}>
     <g transform="translate(-5,-4) scale(.78) rotate(-6 12 12)">${dropGroup}</g>
     <g transform="translate( 5, 4) scale(.78) rotate( 6 12 12)">${dropGroup}</g>
   </svg>`,

  /* 3 — три капли (чуть «хаотичный» уровень по Y) */
  `<svg xmlns="http://www.w3.org/2000/svg" ${SHARED_SVG_ATTRS}>
    <g transform="translate( 0,-7) scale(.72) rotate(-8 12 12)">${dropGroup}</g>  <!-- самая верхняя -->
    <g transform="translate(-6, 4) scale(.72) rotate( 8 12 12)">${dropGroup}</g> <!-- средняя -->
    <g transform="translate( 5, 6) scale(.72) rotate( 0 12 12)">${dropGroup}</g> <!-- самая нижняя -->
   </svg>`,

  /* 4 — капли, вариант A (сжатый ромб) */
  `<svg xmlns="http://www.w3.org/2000/svg" ${SHARED_SVG_ATTRS}>
  <g transform="translate( 0,-6) scale(.72) rotate(-8 12 12)">${dropGroup}</g>  <!-- самая верхняя -->
  <g transform="translate(-9, 2) scale(.70) rotate( 8 12 12)">${dropGroup}</g> <!-- средняя -->
  <g transform="translate( 7, 4) scale(.72) rotate( -6 12 12)">${dropGroup}</g> <!-- чуть нижняя -->
  <g transform="translate( 0, 11) scale(.65) rotate(-8 12 12)">${dropGroup}</g>  <!-- самая нижняя -->
  </svg>`,
];

/* ---------- 0 … 4 «снежинки» ---------- */
// Настройка контура (можно подбирать под тему)
const SNOW_OUTLINE_COLOR = 'rgba(0,0,0,.28)';
const SNOW_OUTLINE_W = 3.2;  // подложка
const SNOW_MAIN_W    = 1.6;  // основной штрих

// Геометрия снежинки (симметричная, 6 лучей)
const snowflakeGeometry = `
  <circle cx="12" cy="12" r="1.2"/>
  ${[0,60,120,180,240,300].map(a => `
    <g transform="rotate(${a} 12 12)">
      <line x1="12" y1="12" x2="12" y2="4"/>
      <line x1="12" y1="4" x2="10.4" y2="5.6"/>
      <line x1="12" y1="4" x2="13.6" y2="5.6"/>
      <line x1="12" y1="7.6" x2="10.8" y2="8.8"/>
      <line x1="12" y1="7.6" x2="13.2" y2="8.8"/>
    </g>
  `).join('')}
  <line x1="12" y1="12" x2="12" y2="9.8"/>
  <line x1="12" y1="12" x2="10.4" y2="10.9"/>
  <line x1="12" y1="12" x2="13.6" y2="10.9"/>
`;

// Группа снежинки: подложка + основной штрих (цвет — currentColor)
const snowflakeGroup = `
  <g fill="none" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke">
    <g stroke="${SNOW_OUTLINE_COLOR}" stroke-width="${SNOW_OUTLINE_W}">
      ${snowflakeGeometry}
    </g>
    <g stroke="currentColor" stroke-width="${SNOW_MAIN_W}">
      ${snowflakeGeometry}
    </g>
  </g>
`;

// 0…4 снежинки — с лёгкими поворотами и масштабом, чтобы не «липли»
const snowSVG = [
  // 0 — пусто
  `<svg xmlns="http://www.w3.org/2000/svg" ${SHARED_SVG_ATTRS}></svg>`,

  // 1 — одна по центру
  `<svg xmlns="http://www.w3.org/2000/svg" ${SHARED_SVG_ATTRS}>
    ${snowflakeGroup}
  </svg>`,

  // 2 — две (чуть меньше и разведены + небольшой поворот)
  `<svg xmlns="http://www.w3.org/2000/svg" ${SHARED_SVG_ATTRS}>
    <g transform="translate(-5,-5) scale(.72) rotate(-8 12 12)">${snowflakeGroup}</g>
    <g transform="translate( 5, 5) scale(.72) rotate(  8 12 12)">${snowflakeGroup}</g>
  </svg>`,

  // 3 — три (компактнее + разный угол)
  `<svg xmlns="http://www.w3.org/2000/svg" ${SHARED_SVG_ATTRS}>
    <g transform="translate( 0,-7) scale(.66) rotate(-6 12 12)">${snowflakeGroup}</g> <!-- верх -->
    <g transform="translate(-6, 6) scale(.66) rotate( 8 12 12)">${snowflakeGroup}</g> <!-- низ-лево -->
    <g transform="translate( 6, 4) scale(.66) rotate( 2 12 12)">${snowflakeGroup}</g> <!-- низ-право -->
  </svg>`,

  // 4 — четыре (ещё чуть меньше + разные углы, чтобы не слипались)
  `<svg xmlns="http://www.w3.org/2000/svg" ${SHARED_SVG_ATTRS}>
    <g transform="translate(-6,-6) scale(.58) rotate(-8 12 12)">${snowflakeGroup}</g>
    <g transform="translate( 6,-6) scale(.58) rotate( 8 12 12)">${snowflakeGroup}</g>
    <g transform="translate(-6, 6) scale(.58) rotate(-3 12 12)">${snowflakeGroup}</g>
    <g transform="translate( 6, 6) scale(.58) rotate( 3 12 12)">${snowflakeGroup}</g>
  </svg>`
];

// 16-рюмбовая роза ветров (для преобразования градусов → румб)
const CARDINAL_DIRECTIONS = [
  "N","NNE","NE","ENE","E","ESE","SE","SSE",
  "S","SSW","SW","WSW","W","WNW","NW","NNW","N"
];

// Румб → градусы (для парсинга строкового bearing)
const CARDINAL_TO_DEG = {
  N:0, NNE:22.5, NE:45, ENE:67.5, E:90, ESE:112.5, SE:135, SSE:157.5,
  S:180, SSW:202.5, SW:225, WSW:247.5, W:270, WNW:292.5, NW:315, NNW:337.5
};

const normalizeDeg = (x) => ((x % 360) + 360) % 360;

// Универсальный парсер bearing → градусы [0..360)
// Принимает: число, "45", "NE", "ssw", и т.п.
const parseBearing = (raw) => {
  if (raw == null) return NaN;

  // 1) число
  if (typeof raw === "number" && Number.isFinite(raw)) {
    return normalizeDeg(raw);
  }

  // 2) строка → число?
  const s = String(raw).trim().toUpperCase();
  if (!s) return NaN;
  const n = Number(s);
  if (Number.isFinite(n)) return normalizeDeg(n);

  // 3) строка → румб?
  if (s in CARDINAL_TO_DEG) return CARDINAL_TO_DEG[s];

  return NaN;
};

// Градусы → краткий румб (N/NE/.../NNW)
const bearingToCardinal = (deg) => {
  const n = Number(deg);
  if (!Number.isFinite(n)) return "";
  const a = normalizeDeg(n);
  // eslint-disable-next-line no-bitwise
  const idx = (((a + 11.25) / 22.5) | 0) % 16;
  return CARDINAL_DIRECTIONS[idx];
};

// Универсально: любой bearing (число/строка) → краткий румб
const toCardinal = (bearing) => {
  const deg = parseBearing(bearing);
  return Number.isFinite(deg) ? bearingToCardinal(deg) : "";
};

// Локализация румба (если нет перевода — вернёт краткий)
const localizeCardinal = (hass, short) =>
  hass?.localize?.(`ui.card.weather.cardinal_direction.${short.toLowerCase()}`) || short;

// ЕДИНАЯ функция отрисовки стрелки направления ветра.
// toDirection=true — стрелка указывает КУДА дует (bearing + 180), false — ОТКУДА дует.
const createWindDirIcon = (bearing, mode, { toDirection = true } = {}) => {
  const deg = parseBearing(bearing);
  if (!Number.isFinite(deg)) return null;

  const rot = toDirection ? (deg + 180) % 360 : deg;

  const dirEl = document.createElement("ha-icon");
  dirEl.icon = "mdi:navigation";
  dirEl.style.cssText = `
    display: inline-flex;
    --mdc-icon-size: ${mode === "focus" ? ".8em" : "1em"};
    transform: rotate(${rot}deg);
    transform-origin: 50% 50%;
    transition: transform 200ms ease;
  `;
  dirEl.setAttribute("title", toDirection ? "Wind →" : "Wind ←");
  return dirEl;
};

/**
 * Универсальная стрелка направления ветра.
 * - bearing: число/строка/румб (например, 270, "270", "WSW")
 * - options:
 *    toDirection: bool — true: «КУДА» (deg + 180), false: «ОТКУДА»
 *    prefer: "auto" | "mdi" | "svg" — способ отрисовки
 *    mode: "focus" | "standard" | "minimal" — влияет на размер для MDI
 *    size: number — размер для SVG (px), для MDI используется --mdc-icon-size
 *    color: CSS color — цвет стрелки
 *    hass: объект hass для локализации румба (опционально)
 *    aria: bool — добавить aria-атрибуты
 */
const createWindDir = (
  bearing,
  {
    toDirection = true,
    prefer = "auto",
    mode = undefined,
    size = 14,
    color = "currentColor",
    hass = null,
    aria = true,
  } = {}
) => {
  const deg = parseBearing(bearing);
  if (!Number.isFinite(deg)) return null;

  const rot = toDirection ? (deg + 180) % 360 : deg;
  const short = toCardinal(deg);                           // "N", "NE", ...
  const localized = short ? localizeCardinal(hass, short) : "";
  const title = `${Math.round(deg)}°${localized ? ` ${localized}` : ""}`;

  // Выбираем рендер: MDI (ha-icon) или SVG
  const canUseMdi = typeof customElements !== "undefined" && !!customElements.get("ha-icon");
  const useMdi = prefer === "mdi" || (prefer === "auto" && canUseMdi);

  if (useMdi) {
    const el = document.createElement("ha-icon");
    el.icon = "mdi:navigation";
    // Если mode не задан — используем size как px для --mdc-icon-size
    const iconSize = mode ? (mode === "focus" ? ".8em" : "1em") : `${size}px`;
    el.style.cssText = `
      display:inline-flex;
      --mdc-icon-size:${iconSize};
      transform: rotate(${rot}deg);
      transform-origin: 50% 50%;
      transition: transform 200ms ease;
      color:${color};
    `;
    el.setAttribute("title", title);
    if (aria) {
      el.setAttribute("role", "img");
      el.setAttribute("aria-label", title);
    }
    return el;
  }

  // SVG-отрисовка (без зависимостей)
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("width", String(size));
  svg.setAttribute("height", String(size));
  svg.style.cssText = `
    display:inline-block;
    transform: rotate(${rot}deg);
    transform-origin: 50% 50%;
    color:${color};
    opacity:.8;
  `;
  // форма стрелки в стиле mdi:navigation
  svg.innerHTML = `<path d="M12 2l4 6h-3v14h-2V8H8l4-6z" fill="currentColor"/>`;

  const t = document.createElementNS("http://www.w3.org/2000/svg", "title");
  t.textContent = title;
  svg.appendChild(t);

  if (aria) {
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", title);
  }

  return svg;
};

// 1) Юнит скорости → м/с
const toMS = (val, unitRaw) => {
  const v = Number(val);
  if (!Number.isFinite(v)) return NaN;
  const u = String(unitRaw || "m/s").toLowerCase().trim();
  switch (u) {
    case "m/s": case "mps": return v;
    case "km/h": case "kmh": return v / 3.6;
    case "mi/h": case "mph": return v * 0.44704;
    case "ft/s": case "fts": return v * 0.3048;
    case "kn": case "kt": case "kts": case "knot": case "knots": return v * 0.514444;
    default: return v; // считаем как м/с, если пришло что-то экзотичное
  }
};

// 2) Границы Бофорта (м/с) — из таблицы «Modern scale»
const BEAUFORT_MPS_BOUNDS = [0.2, 1.5, 3.3, 5.4, 7.9, 10.7, 13.8, 17.1, 20.7, 24.4, 28.4, 32.6];
const beaufortFromMS = (ms) => {
  const v = Math.max(0, Number(ms) || 0);
  for (let b = 0; b < BEAUFORT_MPS_BOUNDS.length; b++) {
    if (v <= BEAUFORT_MPS_BOUNDS[b]) return b;
  }
  return 12;
};

// 3) Палитра цветов «как на Википедии» (цвет фона в ячейке Beaufort number 0..12)
const BEAUFORT_COLORS_HEX = [
  "#FFFFFF", // 0
  "#AEF1F9", // 1
  "#96F7DC", // 2
  "#96F7B4", // 3
  "#6FF46F", // 4
  "#73ED12", // 5
  "#A4ED12", // 6
  "#DAED12", // 7
  "#EDC212", // 8
  "#ED8F12", // 9
  "#ED6312", // 10
  "#ED2912", // 11
  "#D5102D", // 12
];

// 4) HEX → rgba(...) с нужной прозрачностью
const hexToRgba = (hex, alpha = 1) => {
  const h = String(hex).replace("#", "").trim();
  const m = h.length === 3
    ? h.split("").map(x => parseInt(x + x, 16))
    : h.length === 6
      ? [h.slice(0,2),h.slice(2,4),h.slice(4,6)].map(x => parseInt(x,16))
      : [255,255,255];
  return `rgba(${m[0]}, ${m[1]}, ${m[2]}, ${alpha})`;
};

// 5) Цвет по Бофорту «как у Википедии»
const beaufortColorWiki = (b, alpha = 0.9) => {
  const idx = Math.max(0, Math.min(12, b|0));
  return hexToRgba(BEAUFORT_COLORS_HEX[idx], alpha);
};


/* хелпер: проставить width/height */
function sized(svgStr, em = 1.0) {
  return svgStr.replace('<svg ', `<svg width="${em}em" height="${em}em" `);
}

/**
 * Возвращает, сколько часов «покрывает» ОДИН элемент прогноза.
 * @param {"hourly"|"twice_daily"|"daily"} type
 * @param {Array} items — тот самый массив forecast
 */
function slotHours(type, items) {
  if (type === "hourly") {
    /* ―― пытаемся вычислить шаг как разницу между двумя первыми точками ―― */
    if (items.length > 1) {
      const dt0 = new Date(items[0].datetime);
      const dt1 = new Date(items[1].datetime);
      const diffH = Math.round(Math.abs(dt1 - dt0) / 3_600_000);
      // если получили 2, 3, 6 … часов — используем; иначе fallback = 1
      if (diffH >= 1 && diffH <= 6) return diffH;
    }
    return 1;                  // дефолт: 1 ч
  }
  return type === "twice_daily" ? 12 : 24;
}

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

// Нормализация юнита HA: "°C"/"°F" → "C"/"F" (поддержит и "celsius"/"fahrenheit")
function _normTempUnit(unit) {
  const u = String(unit || "").trim().toUpperCase();
  if (u.includes("F")) return "F";
  if (u.includes("K")) return "K"; // на всякий случай
  return "C";
}

/**
 * Маппинг температуры в цвет (hsla) с учётом юнита HA.
 * -40..0 → 280°→180° (фиолетовый→циан) — линейно
 *  0..+40 → 180°→0° (циан→красный) — экспонента 0.6
 * @param {number} temp  — температура (в юните unit)
 * @param {number} [alpha=1] — непрозрачность 0..1
 * @param {string} [unit="°C"|"°F"] — юнит из HA, можно "°C"/"°F"/"C"/"F"/"celsius"/"fahrenheit"
 * @returns {string} hsla(...)
 */
function mapTempToColor(temp, alpha = 1, unit = "°C") {
  if (!Number.isFinite(temp)) return `hsla(0, 0%, 50%, ${alpha})`;

  const u = _normTempUnit(unit);
  let tC = temp;
  if (u === "F") tC = (temp - 32) * (5 / 9);
  else if (u === "K") tC = temp - 273.15;

  const t = Math.max(-40, Math.min(40, tC));
  let hue;
  if (t <= 0) {
    const ratio = (t + 40) / 40; // 0..1
    hue = 280 - ratio * 100;     // 280→180
  } else {
    const ratio = t / 40;
    const adj   = Math.pow(ratio, 0.6);
    hue = 180 - adj * 180;       // 180→0
  }
  return `hsla(${hue.toFixed(1)}, 100%, 50%, ${alpha})`;
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
      only_silam: "",
      display_attribute: "",
      additional_forecast_mode: "standard",
      value_attributes_left:    [],
      value_attributes_right:   [],
      value_attributes_as_rows: false,
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
    if (this._unsub) {
      this._unsub();
      this._unsub = null;
    }
    if (this._unsubP) {
      this._unsubP.then(fn => { fn(); this._unsubP = null; });
    }
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
      cols  = "minmax(0, 1fr)";
      rows  = includeTitle ? "auto auto 1fr" : "auto 1fr";
      areas = includeTitle
        ? `"title" "header" "bars"`
        : `"header" "bars"`;
    } else {
      // standard — три колонки: [header] | [divider] | [bars]
      cols  = "126px 1px minmax(0, 1fr)";
      rows  = includeTitle ? "auto auto" : "auto";
      areas = includeTitle
        ? `"title  vdiv  bars" "header vdiv  bars"`
        : `"header vdiv  bars"`;
    
      // равные отступы до разделителя, растущие с шириной контейнера
      colGap = "column-gap: clamp(2px, 3cqw, 38px); align-items: center;";
    }      

    wrapper.style.cssText = `
      display: grid;
      width: 100%;
      box-sizing: border-box;
      min-width: 0;

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
      font-size: ${mode === "focus" ? "1em" : "1.1em"};
      ${mode === "focus"
        ? `align-items: center;
          width: 100%; margin-bottom: 2px;`
        : `justify-content: center;`
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
    header.classList.add("header-info");
    header.style.cssText = `
      display: flex;
      flex-direction: ${mode === "focus" ? "row"    : "column"};
      align-items: ${mode === "focus" ? "": ""};
      gap:           ${mode === "focus" ? "3px"    : "2px"};
      ${mode === "focus"
        ? `width: 100%; margin-bottom: 4px;`
        : ``
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
        gap: ${mode === "focus" ? "3px" : "1px"};
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
      align-items: ${mode === "focus" ? "" : "center"};
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
   * Создаёт контейнер для иконки нужного размера и стиля.
   * @param {string} iconName — mdi-имя иконки (например "mdi:weather-rainy")
   * @param {"standard"|"focus"} mode — режим карточки
   * @param {string} [customStyles] — дополнительные inline-стили
   * @returns {HTMLElement} — оборачивающий div с иконкой внутри
   */
  _createIconContainer(iconName, mode, customStyles = "") {
    const size = mode === "focus" ? "1.1em" : "1.9em";
    const container = document.createElement("div");
    container.classList.add("icon-container");
    container.style.cssText = `
      display: inline-flex;
      align-items: ${mode === "focus" ? "baseline" : "center"};
      justify-content: center;
      ${customStyles}
    `;
    const iconEl = document.createElement("ha-icon");
    iconEl.icon = iconName;
    iconEl.style.cssText = `
      display: inline-flex;
      --mdc-icon-size: ${size};
      flex: 0 0 ${size};
    `;
    container.appendChild(iconEl);
    return container;
  }
  /**
   * Создаёт контейнер для текстового значения с нужным стилем.
   * @param {string} text — текстовое значение для отображения
   * @param {"standard"|"focus"} mode — режим карточки
   * @param {string} [customStyles] — дополнительные inline-стили
   * @returns {HTMLElement} — оборачивающий div с span внутри
   */
  _createTextContainer(text, mode, customStyles = "") {
    const fontSize   = mode === "focus" ? "0.9em" : "1em";
    const fontWeight = mode === "focus" ? "300"   : "400";
    const container = document.createElement("div");
    container.classList.add("text-container");
    container.style.cssText = `
      display: inline-flex;
      align-items: ${mode === "focus" ? "baseline" : "center"};
      line-height: 1.25;
      font-size: ${fontSize};
      font-weight: ${fontWeight};
      ${customStyles}
    `;
    const span = document.createElement("span");
    span.textContent = text;
    container.appendChild(span);
    return container;
  }
  /**
   * Рендер min/max (без юнитов).
   * В "focus" — строка "min / max"; в "standard" — вертикальный стек.
   *
   * @param {string} minText
   * @param {string} maxText
   * @param {"standard"|"focus"} mode
   * @param {string} [customStyles] — опциональные inline-стили
   * @returns {HTMLElement}
   */
  _createMinMaxStack(minText, maxText, mode, customStyles = "") {
    // В фокусе: компактная строка "min / max"
    if (mode === "focus") {
      return this._createTextContainer(
        `(${minText}/${maxText})`,
        mode,
        `
          display: inline-flex;
          padding-left: 1px;
          font-size: .75em;
          line-height: 1;
          color: var(--secondary-text-color);
          ${customStyles}
        `
      );
    }

    // В стандартном режиме: вертикальный стек
    const wrap = document.createElement("div");
    wrap.classList.add("minmax-stack");
    wrap.style.cssText = `
      display: flex;

      ${customStyles}
    `;

    const mk = (txt) => {
      const el = document.createElement("div");
      el.textContent = txt;
      el.style.cssText = `
        display: inline-flex;
        font-size: .70em;
        line-height: 1;
        color: var(--secondary-text-color);
        white-space: nowrap;
      `;
      return el;
    };

    wrap.append(mk(`(${minText}/${maxText})`));
    return wrap;
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
        /* ---- BEGIN weatherSVGStyles ---- */
        .rain { fill: var(--weather-icon-rain-color, #30b3ff); }
        .sun  { fill: var(--weather-icon-sun-color, #fdd93c); }
        .moon { fill: var(--weather-icon-moon-color, #fcf497); }
        .cloud-back  { fill: var(--weather-icon-cloud-back-color, #d4d4d4); }
        .cloud-front { fill: var(--weather-icon-cloud-front-color, #f9f9f9); }
        .snow {
          fill: var(--weather-icon-snow-color, #f9f9f9);
          stroke: var(--weather-icon-snow-stroke-color, #d4d4d4);
          stroke-width: 1;
          paint-order: stroke;
        }
        .forecast-image-icon {
          width: 36px;
          height: 36px;
        }
        /* ---- END weatherSVGStyles ---- */
        .status-text {
          font-size: clamp(1em, 5vw, 2em);
          margin: 0;
          line-height: 0.9;    /* плотный межстрочный интервал */
        }
        .value-flex {
          display: inline-flex;
          align-items: center;
          font-size: 0.9em;
          line-height: 1;
        }
        /* по умолчанию: скрываем скролл, но резервируем место */
        .hover-scroll {
          overflow-x: auto;
          overflow-y: hidden;
          -webkit-overflow-scrolling: touch;

          /* Firefox: тонкий, но прозрачный ⇒ место зарезервировано */
          scrollbar-width: thin;
          scrollbar-color: transparent transparent;
        }

        /* WebKit: резервируем трек, даже когда невидимо */
        .hover-scroll::-webkit-scrollbar {
          height: 6px;            /* высота дорожки */
          background: transparent; /* невидимый фон */
        }

        /* WebKit: ползунок невидим по умолчанию */
        .hover-scroll::-webkit-scrollbar-thumb {
          background: transparent;
          border-radius: 3px;
        }

        /* на hover: активируем цвет ползунка */
        .hover-scroll:hover {
          /* Firefox: thumb color + прозрачный трек */
          scrollbar-color: var(--scrollbar-thumb-hover-color) transparent;
        }

        /* WebKit: на hover меняем только thumb */
        .hover-scroll:hover::-webkit-scrollbar-thumb {
          background: var(--scrollbar-thumb-hover-color);
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
      .header-container .attrs-flex  {
          flex-direction: row;
          gap: 8px;                 /* расстояние между колонками */
        }
        /* когда ширина ≤ 250 px — колонки становятся рядами */
        @container (max-width: 250px) {
          .header-container .attrs-flex {
            flex-direction: column;   /* одна колонка */
            gap: 2px;                 /* межстрочный отступ */
          }
        }

      .wrapper-container .header-info  {
          flex-wrap: wrap;
        }
        @container (max-width: 280px) {
          .wrapper-container .header-info {
            flex-wrap: wrap;
          }
        }
      .wrapper-container .title-info {
      }
      /* обычное состояние */
      .wrapper-container .title-info--row {
        flex-direction: row;
        gap: 5px;
      }
      .wrapper-container .title-info--col {
        flex-direction: column;
        white-space: normal;
        word-break: break-word;
        align-items: flex-end;
        gap: 1px;
      }
      /* при узком контейнере всегда колонка */
      @container (max-width: 250px) {
        .wrapper-container .title-info--row,
        .wrapper-container .title-info--col {
          flex-direction: column !important;
          gap: 0px          !important;
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
    const isSilamSource = stateObj.attributes.attribution === "Powered by silam.fmi.fi";
    const digits = this._cfg.show_decimals ? 1 : 0;
    const entityTemperatureUnit =
      stateObj.attributes.temperature_unit
      || this.hass.config.unit_system.temperature
      || "°C";

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
      // Определяем, день или ночь (можно вынести наружу, если уже есть)
      const sun = this._hass.states["sun.sun"];
      const nightTime = sun
        ? sun.state !== "above_horizon"
        : new Date().getHours() < 6 || new Date().getHours() >= 18;

      // Пытаемся получить готовый <svg> из вашей функции
      const svgIcon = getWeatherStateSVG(stateObj.state, nightTime);

      let iconEl;
      if (svgIcon) {
        // 1) если SVG вернулся — используем его
        iconEl = svgIcon;
        iconEl.setAttribute("width",  "64");
        iconEl.setAttribute("height", "64");
        iconEl.style.cssText = `
          width: 64px;
          height: 64px;
          flex: 0 0 64px;
        `;
      } else {
        // 2) фоллбек на ha-state-icon для любых остальных состояний
        iconEl = document.createElement("ha-state-icon");
        iconEl.hass     = this._hass;
        iconEl.stateObj = stateObj;
        iconEl.style.cssText = `
          display: flex;
          --mdc-icon-size: 64px;
          flex: 0 0 64px;
        `;
      }
      
      if (isSilamSource) {
        // для Silam — всегда штатный ha-state-icon
        iconEl = document.createElement("ha-state-icon");
        iconEl.hass     = this._hass;
        iconEl.stateObj = stateObj;
        iconEl.style.cssText = `
        display: flex;
        --mdc-icon-size: 64px;
        flex: 0 0 64px;
      `;
      } else {
        // для прочих пробуем SVG
        const svgIcon = getWeatherStateSVG(stateObj.state, nightTime);
        if (svgIcon instanceof SVGSVGElement && svgIcon.hasChildNodes()) {
          iconEl = svgIcon;
          iconEl.setAttribute("width",  "64");
          iconEl.setAttribute("height", "64");
          iconEl.style.cssText = `
            width: 64px;
            height: 64px;
            flex: 0 0 64px;
          `;
        } else {
          // fallback — если SVG нет или пуст, рисуем штатный ha-state-icon
          iconEl = document.createElement("ha-state-icon");
          iconEl.hass     = this._hass;
          iconEl.stateObj = stateObj;
          iconEl.style.cssText = `
          display: flex;
          --mdc-icon-size: 64px;
          flex: 0 0 64px;
        `;
        }
      }
      // контейнер для Имя состояния + friendly_name
      const col1a = document.createElement("div");
      col1a.style.cssText = `
        display: flex;
        justify-content: center;
        flex-direction: column;
        gap: 6px;
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
        const val = this._hass.formatEntityAttributeValue(stateObj, key);
        const value = (val == null || val === "unknown") ? "?" : val;
        const valueDiv = document.createElement("div");
        valueDiv.textContent = value;
        valueDiv.style.cssText = `
          display: inline-flex;
          line-height: 0.9;
          font-size: 0.9em;
          color: var(--primary-text-color);
        `;
        textWrapper.append(valueDiv);

        // 3b) строка-placeholder с динамическим контентом
        // вычисляем текст для placeholder
        let placeholderText = "";
        const forecastType = this._cfg.forecast_type;
        // используем те же items, что и для графика:
        const items = arr.slice(0, this._cfg.forecast_slots ?? arr.length);
        const localeOptions = this.hass.locale || {};
        const fmtOpts = { minimumFractionDigits: digits, maximumFractionDigits: digits };
        // достаём unit из атрибутов сущности
        const unitAttr = `${key}_unit`;
        const unit     = stateObj.attributes[unitAttr] || "";
        if (forecastType === "hourly") {
          // min/max за все hourly-слоты
          const vals = items.map(i => i[key]).filter(v => v != null);
          if (vals.length) {
            const mn = Math.min(...vals);
            const mx = Math.max(...vals);
            const mnFmt = this._formatNumberInternal(mn,  localeOptions, { minimumFractionDigits: digits, maximumFractionDigits: digits });
            const mxFmt = this._formatNumberInternal(mx, localeOptions, { minimumFractionDigits: digits, maximumFractionDigits: digits });
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

      // 4) value_attribute — два столбца или два ряда, в зависимости от настройки
      // ------------------------------------------------------------
      // 1) Берём список из конфига и отфильтровываем реально существующие атрибуты
      const leftAttrs  = this._cfg.value_attributes_left  || [];
      const rightAttrs = this._cfg.value_attributes_right || [];

      const left  = leftAttrs.filter(attr => stateObj.attributes[attr] != null);
      const right = rightAttrs.filter(attr => stateObj.attributes[attr] != null);

      // 2) Опция: true — рисуем двумя рядами, false — двумя столбцами
      const useRows = Boolean(this._cfg.value_attributes_as_rows);

      // 3) Если есть хоть один атрибут — рисуем
      if (left.length || right.length) {
        if (useRows) {
          // ==== РЕЖИМ «ДВА РЯДА» ====
          const rowsContainer = document.createElement("div");
          rowsContainer.style.cssText = `
            display: flex;
            flex-direction: column;
            gap: 2px;
            width: 100%;
          `;

          // Первая строка: left
          if (left.length) {
            const leftRow = document.createElement("div");
            leftRow.style.cssText = `
              display: flex;
              flex-wrap: wrap;
              gap: 4px;
              justify-content: space-between;
            `;
            left.forEach(attr => {
              const el = this._createAttributeValueEl(attr, stateObj);
              el.style.color = 'var(--primary-text-color)';
              // Если есть иконка — перекрашиваем её в свой цвет
              const iconEl = el.querySelector('ha-icon');
              if (iconEl) {
                iconEl.style.color = 'var(--state-icon-color)';
              }
              leftRow.appendChild(el);
            });
            rowsContainer.appendChild(leftRow);
          }

          // Вторая строка: right
          if (right.length) {
            const rightRow = document.createElement("div");
            rightRow.style.cssText = `
              display: flex;
              flex-wrap: wrap;
              gap: 4px;
              justify-content: space-between;
            `;
            right.forEach(attr => {
              const el = this._createAttributeValueEl(attr, stateObj);
              el.style.color = 'var(--primary-text-color)';
              // Если есть иконка — перекрашиваем её в свой цвет
              const iconEl = el.querySelector('ha-icon');
              if (iconEl) {
                iconEl.style.color = 'var(--state-icon-color)';
              }
              rightRow.appendChild(el);
            });
            rowsContainer.appendChild(rightRow);
          }

          header.appendChild(rowsContainer);

        } else {
          // ==== РЕЖИМ «ДВА СТОЛБЦА» (flex) ====
          const valueFlex = document.createElement("div");
          valueFlex.classList.add("attrs-flex");          // ⬅ для container-query
          valueFlex.style.cssText = `
            display: flex;
            width: 100%;
          `;

          /* левый столбец */
          const leftCol = document.createElement("div");
          leftCol.style.cssText = `
            display: flex;
            flex-direction: column;
            gap: 2px;
            flex: 1 1 0;              /* тянется */
          `;
          left.forEach(attr => {
            const el = this._createAttributeValueEl(attr, stateObj);
            el.style.cssText += `
              color: var(--primary-text-color);
              white-space: nowrap;
            `;
            const iconEl = el.querySelector('ha-icon');
            if (iconEl) {
              iconEl.style.color = 'var(--state-icon-color)';
            }
            leftCol.appendChild(el);
          });
          valueFlex.appendChild(leftCol);

          /* правый столбец */
          const rightCol = document.createElement("div");
          rightCol.style.cssText = `
            display: flex;
            flex-direction: column;
            gap: 2px;
            flex: 0 0 auto;           /* ширина по содержимому */
          `;
          right.forEach(attr => {
            const el = this._createAttributeValueEl(attr, stateObj);
            el.style.cssText += `
              color: var(--primary-text-color);
              white-space: nowrap;
            `;
            const iconEl = el.querySelector('ha-icon');
            if (iconEl) {
              iconEl.style.color = 'var(--state-icon-color)';
            }
            rightCol.appendChild(el);
          });
          valueFlex.appendChild(rightCol);

          header.appendChild(valueFlex);
        }
      }
      // дальше остальной рендер (bars, forecast и т.д.) продолжается…

      // Вставляем header
      this._body.appendChild(header);
      // Отдельный divider вместо border-bottom у header col1a
      if (hasForecast && mode === "show_both") {
        const divider = document.createElement("div");
        divider.style.cssText = `
          width: 100%;
          border-bottom: 1px solid var(--divider-color);
          margin-top: 12px; /* отступ сверху/снизу */
        `;
        this._body.appendChild(divider);
      }
    }
  // --------------------
  // Разделитель + имя
  // --------------------
  // 1) Понятное имя
  const friendlyEl = document.createElement("div");
  friendlyEl.textContent = stateObj.attributes.friendly_name || "";
  friendlyEl.style.cssText = `
    display: inline-flex;
    line-height: 1;
    font-size: 1em;
  `;
  // 2) Атрибутив имя
  const attributionEl = document.createElement("div");
  attributionEl.textContent = stateObj.attributes.attribution || "";
  attributionEl.style.cssText = `
    display: inline-flex;
    color: var(--secondary-text-color);
    line-height: 1;
    font-size: 0.8em;
  `;
  // 3) Собираем оба элемента в одну строку
  const basetitleRow = document.createElement("div");
  basetitleRow.style.cssText = `
    display: flex;
    flex-direction: row;
    align-items: baseline;
    flex-wrap: wrap;
    gap: 4px;
    padding-bottom: 4px; /* при необходимости */
    width: 100%;
    border-bottom: 1px solid var(--divider-color);
  `;
  basetitleRow.append(friendlyEl, attributionEl);
  if (hasForecast && this._cfg.forecast === "show_forecast") {
    this._body.appendChild(basetitleRow);
  }
  // --------------------
  // 2) ГРАФИЧЕСКИЙ БЛОК (прогноз)
  // --------------------
  if ((mode !== "show_current") && hasForecast) {
    // === Существующий блок с иконками ===
    if (["hourly", "twice_daily", "daily"].includes(this._cfg.forecast_type)
        && Array.isArray(arr) && arr.length) {
      const lang = this._hass.language || "en";
      const slots = this._cfg.forecast_slots ?? arr.length;
      const items = arr.slice(0, slots);
      
      const wrapperchart = document.createElement("div");
      wrapperchart.classList.add("hover-scroll");
      wrapperchart.style.cssText = `
        position: relative;
        flex: 1 1 auto;
        min-width: 0;
        box-sizing: border-box;
        padding-top: 12px;
      `;
      const chart = document.createElement("div");
      chart.style.cssText = `
        display: flex;
        gap: 8px;
        width: 100%;
        box-sizing: border-box;
      `;
      // ───────────────────────────────────────────
      const hSlot = slotHours(this._cfg.forecast_type, items);
      // ───────────────────────────────────────────
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

        let slotNight = false;
        if ("is_daytime" in i) {
          slotNight = i.is_daytime === false;
        } else if ("sun.sun" in this._hass.states) {
          // fallback: сравниваем datetime слота с вершинами sun.sun
          const sun = this._hass.states["sun.sun"];
          const t   = new Date(i.datetime).getTime();
          const dawn = new Date(sun.attributes.next_dawn).getTime();
          const dusk = new Date(sun.attributes.next_dusk).getTime();
          slotNight = t < dawn || t >= dusk;
        } else {
          // самый грубый вариант
          const h = new Date(i.datetime).getHours();
          slotNight = h < 6 || h >= 18;
        }

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
        let iconEl;

        if (isSilamSource) {
          // ── SILAM: остаётся прежнее отображение mdi-иконок ──
          const iconName = forecastIcons.state[i.condition] || forecastIcons.default;
          iconEl = document.createElement("ha-icon");
          iconEl.icon = iconName;
        } else {
          // ── «обычные» интеграции ──
          const svgIcon = getWeatherStateSVG(i.condition, slotNight);

          if (svgIcon) {
            // получили полноценный SVG ⇒ используем его
            iconEl = svgIcon;
            iconEl.setAttribute("width",  "64");
            iconEl.setAttribute("height", "64");
            iconEl.style.cssText = `
              width: 64px;
              height: 64px;
              flex: 0 0 64px;
            `;
          } else {
            // fallback: штатный ha-state-icon
            iconEl = document.createElement("ha-state-icon");
            iconEl.hass     = this._hass;
            iconEl.stateObj = {
              entity_id: "weather.forecast",
              state:     i.condition,
              attributes:{}
            };
          }
        }

        // 3) Общие стили (одинаковые для SVG и ha-иконок)
        iconEl.style.cssText = `
          width: 2.2em;
          height: 2.2em;
          flex: 0 0 2.2em;
          margin: 4px 0;
        `;

        // 4) Добавляем иконку в колонку
        col.appendChild(iconEl);

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
            { minimumFractionDigits: digits, maximumFractionDigits: digits }
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
            { minimumFractionDigits: digits, maximumFractionDigits: digits }
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
        wrapperchart.appendChild(chart);
        this._body.appendChild(wrapperchart);
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
          const hassObj = this._hass || this.hass;
          const digitsCommon = Number(this._cfg?.pollen_digits ?? this._cfg?.digits ?? 0);

          const minimalRow = document.createElement("div");
          minimalRow.style.cssText = `
            display: flex;
            flex-wrap: wrap;
            justify-content: space-evenly;
            gap: 16px;
            padding: 8px 0;
          `;

          // безопасно берём первый слот прогноза (arr у вас уже используется выше)
          const fcst0 = (Array.isArray(arr) && arr.length) ? arr[0] : null;

          availableAttrs.forEach(attr => {
            const stateVal    = stateObj?.attributes?.[attr];
            const forecastVal = fcst0 && fcst0[attr] != null ? fcst0[attr] : null;
            const rawVal      = (stateVal != null) ? stateVal : forecastVal;
            const fromForecast = (stateVal == null && forecastVal != null);

            // Числовое значение (если возможно)
            const numVal = rawVal == null ? null : Number(rawVal);
            const hasNum = Number.isFinite(numVal);

            // Пыльца: шкала и цвет
            const pollenType = attr.startsWith("pollen_") ? attr.slice(7) : attr;
            const scale      = (typeof POLLEN_SCALES !== "undefined") ? POLLEN_SCALES[pollenType] : undefined;

            const iconName = (
              (typeof weatherAttrIcons !== "undefined" && weatherAttrIcons && weatherAttrIcons[attr]) ||
              "mdi:flower-pollen"
            );

            let iconColor = "var(--primary-text-color)";
            if (scale && hasNum) {
              let idx = 0;
              for (let i = scale.thresholds.length - 1; i >= 0; i--) {
                if (numVal >= scale.thresholds[i]) { idx = i; break; }
              }
              iconColor = scale.colors[idx] ?? iconColor;
            }

            /* ---- карточка атрибута ---- */
            const hdr = document.createElement("div");
            hdr.style.cssText = `
              display: flex;
              flex-direction: column;
              align-items: center;
              width: 64px;
            `;

            /* иконка */
            const iconEl = document.createElement("ha-icon");
            iconEl.icon = iconName;
            iconEl.style.cssText = `
              --mdc-icon-size: 2.5em;
              color: ${iconColor};
              margin-bottom: 4px;
            `;
            hdr.appendChild(iconEl);

            /* локализованное имя */
            const nameEl = document.createElement("span");
            nameEl.textContent = hassObj.formatEntityAttributeName(stateObj, attr);
            nameEl.style.cssText = `
              font-size: 0.8em;
              text-align: center;
              margin-bottom: 4px;
            `;
            hdr.appendChild(nameEl);

            /* значение */
            const valEl = document.createElement("span");

            // 1) пробуем штатный форматтер HA (только для state-значения)
            let valText = (stateVal != null)
              ? hassObj.formatEntityAttributeValue(stateObj, attr)
              : "";

            // 2) если пусто — форматируем значение из прогноза / сырое значение
            if (valText == null || valText === "") {
              if (rawVal == null) {
                valText = "–";
              } else if (attr === "precipitation_probability" || attr === "humidity" || attr === "cloud_coverage") {
                // проценты: округляем
                valText = hasNum ? `${Math.round(numVal)}%` : `${rawVal}%`;
              } else if (attr === "precipitation") {
                // осадки: 1 десятая + юнит
                const unit = stateObj?.attributes?.precipitation_unit || "";
                const v = hasNum ? numVal : Number(rawVal);
                valText = Number.isFinite(v)
                  ? `${this._formatNumberInternal(v, hassObj.locale || {}, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}${unit ? ` ${unit}` : ""}`
                  : String(rawVal);
              } else if (attr === "wind_bearing") {
                // bearing: румб без градусов (если есть наши хелперы)
                try {
                  const short = (typeof toCardinal === "function") ? toCardinal(rawVal) : "";
                  valText = short
                    ? ((typeof localizeCardinal === "function") ? localizeCardinal(hassObj, short) : short)
                    : String(rawVal);
                } catch (_) {
                  valText = String(rawVal);
                }
              } else {
                // прочее: число с общими digits + юнит если есть
                if (hasNum) {
                  valText = this._formatNumberInternal(numVal, hassObj.locale || {}, {
                    minimumFractionDigits: digitsCommon,
                    maximumFractionDigits: digitsCommon
                  });
                  const unit = stateObj?.attributes?.[`${attr}_unit`];
                  if (unit) valText += ` ${unit}`;
                } else {
                  valText = String(rawVal);
                }
              }
            }

            valEl.textContent = valText;
            if (fromForecast) {
              valEl.title = this._labels?.from_forecast || "Из прогноза";
              valEl.style.opacity = "0.85";
              // маленькая точка-индикатор
              const dot = document.createElement("span");
              dot.textContent = "•";
              dot.style.cssText = "margin-left:4px; font-size:0.9em; opacity:.7;";
              valEl.appendChild(dot);
            }
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
        wrapper.classList.add("wrapper-container");  
        wrapper.style.cssText = `
          display: flex;
          gap: 1px;
          width: 100%;
          ${mode === "focus"
            ? `flex-direction: column;`
            : `flex-wrap: wrap; align-items: stretch;`
          }
          /* объявляем контейнер по inline-size (ширине) */
          container-type: inline-size;
        `;
        // нужен флаг, чтобы не нарисовать оверлей дважды
        let weatherOverlayDrawn = false;
        // список «погодных» атрибутов для погодного графика
        const weatherAttrs = [
          "temperature",
          "temperature_low",
          "temperature_high",
          "precipitation_probability",
          "precipitation",
          "humidity",
          "visibility",
          "uv_index",
          "dew_point",
          "wind_bearing",
          "wind_speed",
          "wind_gust_speed",
          "ozone",
          "apparent_temperature",
          "cloud_coverage",
          "pressure"
        ];
        availableAttrs.forEach(attr => {
          // пропускаем осадки в ветке "других графиков"        
          const pollenType = attr.replace("pollen_", "");
          const scale      = POLLEN_SCALES[pollenType];
          const isWeather = weatherAttrs.includes(attr);

          /* -----------------------------------------------------------
            *  Контейнер для каждого блока до прогноза (пыльцы, температуры и т.д. header над гистограммами в focus)
            * --------------------------------------------------------- */
          // 0.1) сам block — это обёртка карточки для каждого атрибута
          const block = this._createBlockContainer(mode);
          // 0.2) wrapper с grid‐лейаутом (создаётся по режиму focus/standard)
          // показываем заголовок, если только прогноз
          // Решаем, нужен ли titleContainer:
          const includeTitle = !isWeather;
          const blockWrapper = this._createBlockWrapper(mode, includeTitle);
          // 0.3) titleContainer (опционально), отдаём в область «title»
          const titleContainer = this._createTitleContainer(mode);
          if (includeTitle) {
            titleContainer.style.gridArea = "title";
            blockWrapper.appendChild(titleContainer);
          }
          // тонкий вертикальный разделитель между header и bars (только для standard)
          if (mode == "standard") {
            const vdiv = document.createElement("div");
            vdiv.style.cssText = `
              grid-area: vdiv;
              background: var(--divider-color);
              width: 1px;
              min-width: 1px;
              align-self: stretch;   /* растянуть по высоте */
              justify-self: center;  /* по центру колонки */
            `;
            blockWrapper.appendChild(vdiv);
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
          const sidePad = 12;           // px — сколько места отвести под “торчащие” иконки
          const cellMinWidth = 16; 
          const padStr  = `${sidePad}px`;
          // Размеры для полоски времени
          const baseTFH = !isSilamSource ? 46 : 35;
          // если forecast_type == "twice_daily" → две строки → +40 %
          const tfh = this._cfg.forecast_type === "twice_daily"
            ? Math.round(baseTFH * (!isSilamSource ? 1.2 : 1.35))
            : baseTFH;

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
            const nameEl = document.createElement("div");
            nameEl.textContent = this._labels[attr] || pollenType;
            nameEl.style.cssText = `
              font-size: ${mode === "focus" ? "0.8em" : "1em"};
              font-weight: ${mode === "focus" ? "400" : "600"};
            `;
            titleContainer.appendChild(nameEl);

            // цвет иконки по текущему значению
            const iconWrapper = document.createElement("div");
            iconWrapper.style.cssText = `
              position: relative;
              display: inline-flex;
              flex: ${mode === "focus" ? "0 0 auto" : "0 0 auto"};
            `;
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
            iconWrapper.appendChild(icon);


            // ─── НОВЫЙ БЛОК: стрелка тренда ───
            let trendEl = null;
            // items — это ваш массив прогнозных точек
            const nextVal = items[0]?.[attr];
            if (nextVal != null) {
            // вычисляем цвет для nextVal
              let nextIconIdx = scale.thresholds.findLastIndex(th => nextVal >= th);
              if (nextIconIdx < 0) nextIconIdx = 0;
              const nextIconColor = scale.colors[nextIconIdx];
              // выбираем иконку
              const trendIcon = nextVal > baseVal
                ? "mdi:trending-up"
                // mdi:trending-up mdi:triangle-small-up mdi:trending-down
                : nextVal < baseVal 
                  ? "mdi:trending-down"
                  // mdi:triangle-small-down mdi:trending-down
                  : "";
              trendEl = document.createElement("ha-icon");
              trendEl.icon = trendIcon;
              trendEl.style.cssText = `
                display: inline-flex;
                --mdc-icon-size: ${mode === "focus" ? "0.8em" : "1.2em"};
                color: ${nextIconColor};
                position: ${mode === "focus" ? "" : "absolute"};
                top: ${mode === "focus" ? "" : "0%"};
                right: ${mode === "focus" ? "" : "-25%"};
                ${mode === "focus"
                  ? `padding-left: 2px;`
                  : ``
                }
              `;
            }
            if (mode === "standard") {
              // сразу рендерим рядом с иконкой пыльцы
              if (trendEl) {
                iconWrapper.appendChild(trendEl);
              }
            } else {
              // в фокусе вставляем следом за именем пыльцы
              if (trendEl) {
                titleContainer.appendChild(trendEl);
              }
              
            }

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
                  padding-left: 3px; `
                : ``
              }
            `;
            // предполагаем, что minLevel и maxLevel уже рассчитаны
            minMaxEl.textContent = `${minLevel} / ${maxLevel}`;
            valueContainer.appendChild(minMaxEl);

            // — добавляем все в baseInfo в нужном порядке—
            const baseElems = mode === "focus"
              ? [ icon, valueContainer ]
              : [ 
                iconWrapper,
                valueContainer ];
            baseInfo.append(...baseElems);

            // — вешаем baseInfo в header —
            header.appendChild(baseInfo);
            
            /* -----------------------------------------------------------
            *  Контейнер мини-гистограммы (overlay + timeFlex + pollenFlex)
            * --------------------------------------------------------- */
            const overlayH    = BAR_CHART_HEIGHT + tfh;

            const overlay = document.createElement("div");
            overlay.classList.add("hover-scroll");
            overlay.style.cssText = `
              position: relative;
              flex: 1 1 auto;
              min-width: 0;
              height: ${overlayH}px;
              box-sizing: border-box;
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
            /* 1) timeFlex — прокручиваемые лейблы времени */
            const timeFlex = document.createElement("div");
            timeFlex.style.cssText = `
              position: absolute;
              top: 0; left: 0; right: 0;
              display: flex;
              flex:1 1 auto; min-width:0; box-sizing:border-box;
              padding-bottom:4px; pointer-events:none;
              padding-inline: 0 ${padStr};
            `;
            items.forEach((i, idx) => {
              const cell = document.createElement("div");
              cell.style.cssText = `
                flex:1 1 0;
                min-width:${cellMinWidth}px;
                width:0;
                display:flex; flex-direction:column;
                align-items:center; text-align:center;
                color:var(--secondary-text-color);
                padding-inline: clamp(1px,2%,5px);
                /* box-sizing:border-box; */
                line-height:1;
                /* еле заметный разделитель справа */
                ${idx < items.length - 1
                  ? `box-shadow: inset -1px 0 0 var(--divider-color);`
                  : ``}                
              `;
              // 1) Метка времени
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
            // -----------------------------------------------------------
            // 2) pollenFlex — сами столбики пыльцы
            // -----------------------------------------------------------
            const pollenFlex = document.createElement("div");
            pollenFlex.style.cssText = `
              position: absolute;
              top: ${tfh}px;      /* сразу под timeFlex */
              left: 0; right: 0;
              display:flex;
              flex:1 1 auto; min-width:0; box-sizing:border-box;
              padding-inline: 0 ${padStr};
            `;
            overlay.appendChild(pollenFlex);
            /* -----------------------------------------------------------
             *  Проход по каждой точке прогноза и формирование группы столбиков
             * --------------------------------------------------------- */
            const now = new Date();
            let nextPeakTime  = Infinity;
            let nextPeakValue = null;
            items.forEach(i => {
              /* ---------------------------------------------------------
               *  Создание контейнера-группы для данного интервала
               * ------------------------------------------------------- */
              const group = document.createElement("div");
              group.style.cssText = `
                position: relative;
                display:flex;
                justify-content: center;
                flex: 1 1 0;
                min-width: ${cellMinWidth}px;
                width: 0;
                /* box-sizing:border-box; */
                padding-inline: clamp(1px,2%,5px);
              `;
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
              pollenFlex.appendChild(group);
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
            
              // создаём wrapper значение\(день\время)
              const peakvalContainer = this._createValueContainer(mode);
              peakvalContainer.classList.add("peak-val-wrapper");
              // 2) Значение пика
              const valEl = document.createElement("div");
              valEl.textContent = `${nextPeakValue}`;
              valEl.style.cssText = `
                display: inline-flex;
                line-height: 1; 
                font-size: ${mode === "focus" ? "0.95em" : "1.2em"};
                font-weight: ${mode === "focus" ? "400" : "600"};
                ${mode === "focus"
                  ? `padding-right: 2px;`
                  : ``
                }
              `;

              // создаём wrapper день\время
              const peakvalueContainer = document.createElement("div");
              peakvalueContainer.style.cssText = `
                display: inline-flex;
                flex-direction: ${mode === "focus" ? "row" : "column"};
                line-height: 1;
                gap: ${mode === "focus" ? "" : "1px"};
                align-items: ${mode === "focus" ? "flex-end" : "flex-end"};
                justify-content: ${mode === "focus" ? "flex-start" : "center"};
                font-size: ${mode === "focus" ? "0.7em" : "1em"};
                color: var(--secondary-text-color);
                ${mode === "focus"
                  ? `border-left: 1px solid var(--divider-color);
                    padding-left: 3px; flex-wrap: wrap;`
                  : ``
                }
            `;
              // 3) День («сегодня», «завтра» или короткий weekday)
              const dt = new Date(nextPeakTime);
              const rawDay = this._formatRelativeDay(dt);
              const dayLabel = this._capitalize(rawDay);

              const dayEl = document.createElement("div");
              dayEl.textContent = dayLabel;
              dayEl.style.cssText = `
              ${mode === "focus"
                ? `padding-right: 2px;`
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
              

              peakvalueContainer.append(dayEl, timeEl);
              peakvalContainer.append(valEl, peakvalueContainer);
              // — добавляем все в baseInfo в нужном порядке—
              const peakElems = mode === "focus"
                ? [ peakIcon, peakvalContainer]
                : [ peakIcon, peakvalContainer];
              peakContainer.append(...peakElems);
              // Добавляем готовый контейнер в header
              header.appendChild(peakContainer);
            }

            /* -----------------------------------------------------------
             *  Вставляем готовый блок пыльцы в DOM
             * --------------------------------------------------------- */
            bars.appendChild(overlay);
            wrapper.appendChild(block);
          }

          // 2) TIME + TEMP FLEX OVERLAY + MIN/MAX/ZERO LINES
          else if (isWeather) {
            if (weatherOverlayDrawn) return;           // выходим из forEach
            weatherOverlayDrawn = true;                // помечаем, что уже нарисовали
            /* —— что реально выбрано пользователем —— */
            const showTemp   = ["temperature", "temperature_low", "temperature_high"].some(a => availableAttrs.includes(a));
            const tempAttr   = ["temperature", "temperature_high", "temperature_low"].find(a => availableAttrs.includes(a)) || null;
            const showProb   = availableAttrs.includes("precipitation_probability");
            const showAmount = availableAttrs.includes("precipitation");

            // ветровые выборы — как просил
            const showWindSpeed = availableAttrs.includes("wind_speed");
            const showWindGust  = availableAttrs.includes("wind_gust_speed");
            const showWindDir   = availableAttrs.includes("wind_bearing");

            const precipBarW = 0.12;        // ширина бара (18 % от ширины температурного)
            const precipColor = "rgba(33,150,243,.55)"; // полупрозрачный синий
            // размеры сегментов гистограммы

            /* —— подготовка рядов/максимумов —— */
            // осадки
            const allProbs   = items.map(i => (showProb   && typeof i.precipitation_probability === "number") ? i.precipitation_probability : 0);
            const maxProb    = showProb ? Math.max(...allProbs, 0) : 0;

            const allAmounts = items.map(i => (showAmount && typeof i.precipitation === "number") ? i.precipitation : 0);
            const maxAmount  = showAmount ? Math.max(...allAmounts, 0) : 0;

            // ветер
            const speeds = showWindSpeed ? items.map(i => Number(i?.wind_speed ?? 0)) : [];
            const gusts  = showWindGust  ? items.map(i => Number(i?.wind_gust_speed ?? (showWindSpeed ? i?.wind_speed : 0))) : [];
            const hasDir = showWindDir && items.some(i => Number.isFinite(Number(i?.wind_bearing)));
            const maxWind = Math.max(0, ...(speeds.length ? speeds : [0]), ...(gusts.length ? gusts : [0]));
            const windUnit = stateObj.attributes.wind_speed_unit || "m/s";

            /* —— флаги наличия данных (после max’ов) —— */
            const hasTemp   = showTemp;
            const hasProb   = showProb && maxProb   > 0;
            const hasAmount = showAmount && maxAmount > 0;
            const hasAnyAmount = showAmount && items.some(i => typeof i.precipitation === "number" && i.precipitation > 0);
            const hasWindData = (showWindSpeed || showWindGust) && maxWind > 0;
            const hasWind     = (showWindSpeed || showWindGust || showWindDir) && (hasWindData || showWindDir) && maxWind > 0;

            /* —— высоты сегментов (px) —— */
            const TEMP_H   = hasTemp   ?  80 : 0;
            const PROB_H   = hasProb   ?  50 : 0;
            const AMOUNT_H = hasAmount ?  15 : 0;   // было 0 — теперь реально резервирует место

            // режимы
            const hasSpeedBars = showWindSpeed && maxWind > 0;
            const hasGustBars  = showWindGust  && maxWind > 0;
            const hasBars      = hasSpeedBars || hasGustBars;

            // низ под числовую подпись скорости
            const VAL_LABEL_H = hasSpeedBars ? 10 : 0;  // высота текста
            const VAL_GAP     = hasSpeedBars ? 4  : 0;  // зазор над текстом                        
            const capBottom = hasBars ? (VAL_LABEL_H + VAL_GAP) : 0;

            // адаптивная высота
            let WIND_H = 0;

            if (hasSpeedBars && hasGustBars && showWindDir) {
              WIND_H = 56; // оба бара + стрелка/лейбл (чуть выше, чтобы уместилась подпись порыва сверху и скорость снизу)
            } else if (hasSpeedBars && hasGustBars && !showWindDir) {
              WIND_H = 32; // оба бара, без стрелки
            } else if (hasBars && showWindDir) {
              WIND_H = 50; // ваш случай: один бар (speed или gust) + стрелка/лейбл
            } else if (hasBars && !showWindDir) {
              WIND_H = 20; // ваш случай: только один бар (speed или gust), компактно
            } else if (!hasBars && showWindDir) {
              WIND_H = 30; // ваш случай: только стрелка/лейбл
            } else {
              WIND_H = 0;  // ничего не выбрано или нет данных
            }

            /* —— сводная высота «температурно-осадочной» части (без ветра!) —— */
            let chartH = 0;
            if (hasTemp)      chartH += TEMP_H;
            else if (hasProb) chartH += PROB_H;
            if (hasAmount)    chartH += AMOUNT_H;

            const AMOUNT_OVERHANG = hasAnyAmount ? Math.round(chartH * 0.25) /* + 8 */ : 0;

            /* —— температура: диапазон для окраски/нулевой линии —— */
            let tMin = 0, tMax = 0, range = 1, useLowExtremes = false;
            if (showTemp && tempAttr) {
              const highs = items.map(i => i[tempAttr]).filter(v => v != null);
              const lows  = items.map(i => i.templow).filter(v => v != null);
              tMin  = lows.length ? Math.min(...lows) : Math.min(...highs);
              tMax  = Math.max(...highs);
              range = tMax - tMin || 1;
              useLowExtremes = lows.length > 0;
            }

            // цвета и отступы
            const colortMax = mapTempToColor(tMax, 0.4, entityTemperatureUnit);
            const colortMin = mapTempToColor(tMin, 0.4, entityTemperatureUnit);
            const colorZero = mapTempToColor(0,   0.4, entityTemperatureUnit);
            const markerH = 12;
            const labelMargin = 8;
            const offset = markerH / 2 + labelMargin;
            const labelPadding = showTemp ? 20 : 6; // запас под подписи min/max/zero

            const TIME_PB = 4;                 // timeFlex: padding-bottom: 4px
            const WIND_PB = hasWind  ? 4 : 0;   // windFlex: padding-bottom: 4px (а не labelPadding)
            const WIND_DIR_PB = showWindDir  ? 2 : 0;
            const TEMP_PT = labelPadding;      // tempFlex: padding-top: labelPadding            

            const OVERLAY_H =
              tfh +                 // высота timeFlex
              TIME_PB +             // его нижний паддинг
              (hasWind ? (WIND_H + WIND_PB + WIND_DIR_PB) : 0) +  // ветрослой + его паддинг
              capBottom +
              chartH +              // температура/осадки
              TEMP_PT +            // верхний запас под подписи температур
              labelPadding +                  // ваш сервисный зазор
              AMOUNT_OVERHANG;      // доп. запас только если рисуем amount с bottom:-25%

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

            // — иконка термометра —
            const iconEl = document.createElement("ha-icon");
            iconEl.icon = "mdi:thermometer";
            iconEl.style.cssText = `
              display: inline-flex;
              --mdc-icon-size: ${mode === "focus" ? "1.1em" : "3.0em"};
              flex: ${mode === "focus" ? "0 0 1.1em" : "0 0 3.0em"};
            `;

            // 1) контейнер для всех значений и статистики
            const valueContainer = document.createElement("div");
            valueContainer.style.cssText = `
              display: inline-flex;
              flex-direction: ${mode === "focus" ? "row" : "column"};
              align-items: ${mode === "focus" ? "baseline" : ""};
              gap: ${mode === "focus" ? "2px" : ""};
              flex-wrap: nowrap;
            `;

            // локаль и число знаков
            const localeOptions = this.hass?.locale || {};
            const digits = Number(this._cfg?.temperature_digits ?? this._cfg?.digits ?? 0);
            const fmtOpts = { minimumFractionDigits: digits, maximumFractionDigits: digits };

            // --- ЮНИТЫ ДЛЯ СВЯЗАННЫХ ПОЛЕЙ ---
            const pickUnit = (attr) => {
              // проценты
              if (attr === "precipitation_probability" || attr === "humidity" || attr === "cloud_coverage") return "%";
              // осадки
              if (attr === "precipitation") return stateObj.attributes.precipitation_unit || "";

              // температура и «родственные»
              if (attr === "apparent_temperature" || attr === "dew_point" || attr === "temperature") {
                return stateObj.attributes.temperature_unit
                    || this.hass?.config?.unit_system?.temperature
                    || "°C";
              }

              // ветер и «родственные»
              if (attr === "wind_speed" || attr === "wind_gust_speed") {
                return stateObj.attributes.wind_speed_unit
                    || stateObj.attributes[`${attr}_unit`]
                    || "m/s"; // безопасный дефолт
              }
              if (attr === "wind_bearing") return "°";

              // прочие поля пробуем взять из `${attr}_unit`
              return stateObj.attributes[`${attr}_unit`] || "";
            };

            // === ТЕКУЩЕЕ ЗНАЧЕНИЕ ТЕМПЕРАТУРЫ — ВСЕГДА ===
            let currentVal =
              stateObj.attributes.temperature != null
                ? stateObj.attributes.temperature
                : (Array.isArray(items) && items.length ? items[0].temperature : null);

            const currentUnit = pickUnit("temperature");

            if (currentVal != null && Number.isFinite(Number(currentVal))) {
              const currentEl = document.createElement("div");
              currentEl.textContent =
                `${this._formatNumberInternal(currentVal, localeOptions, fmtOpts)}\u00A0${currentUnit}`;
              currentEl.style.cssText = `
                display: inline-flex;
                align-items: ${mode === "focus" ? "baseline" : "center"};
                line-height: 1.25;
                font-size: ${mode === "focus" ? "0.9em" : "1.8em"};
                font-weight: ${mode === "focus" ? "500" : "600"};
              `;
              valueContainer.appendChild(currentEl);
            }

            // === MIN/MAX ПО ТИПУ ПРОГНОЗА ===
            let baseMin = null, baseMax = null;
            if (Array.isArray(items) && items.length) {
              const isHourly = this._cfg?.forecast_type === "hourly";
              const toNum = (v) => (typeof v === "number" ? v : NaN);
              const filt = (arr) => arr.map(toNum).filter(Number.isFinite);

              if (isHourly) {
                // часовой: min/max по temperature
                const temps = filt(items.map(i => i.temperature));
                if (temps.length) {
                  baseMin = Math.min(...temps);
                  baseMax = Math.max(...temps);
                }
              } else {
                // дневной: max из temperature, min из templow (если нет templow — берём temperature)
                const highs = filt(items.map(i => i.temperature));
                const lows  = filt(items.map(i => (i.templow ?? i.temperature)));
                if (highs.length) baseMax = Math.max(...highs);
                if (lows.length)  baseMin = Math.min(...lows);
              }
            }

            if (baseMin != null && baseMax != null) {
              const minMaxEl = document.createElement("div");
              minMaxEl.textContent =
                `(${this._formatNumberInternal(baseMin, localeOptions, fmtOpts)}/` +
                `${this._formatNumberInternal(baseMax, localeOptions, fmtOpts)})`;
              minMaxEl.style.cssText = `
                display: inline-flex;
                padding-left: 1px;
                line-height: 1; 
                font-size: ${mode === "focus" ? "0.75em" : "1em"};
                color: var(--secondary-text-color);
              `;
              valueContainer.appendChild(minMaxEl);
            }

            // — добавляем всё в baseInfo —
            const baseElems = [ iconEl, valueContainer ];
            baseInfo.append(...baseElems);

            // === AttrInfo для выбранных атрибутов: группируем осадки и ветер, остальные по-отдельности ===
            let precipContainer;
            let windContainer;
            // === Новый общий контейнер для ВСЕХ атрибутов ===
            const attrContainer = document.createElement("div");
            attrContainer.classList.add("all-attrs");
            attrContainer.style.cssText = `
              display: flex;
              flex-wrap: wrap;
              gap: ${mode === "focus" ? "" : "4px"};
              width:100%;
              box-sizing:border-box;
            `;

            // — если фокус: baseInfo идёт в attrContainer; иначе — сразу в header
            if (mode === "focus") {
              attrContainer.appendChild(baseInfo);
            } else {
              header.appendChild(baseInfo);
            }

            // availableAttrs приходит из this._cfg.additional_forecast, в порядке, заданном пользователем
            availableAttrs.forEach(attr => {
              if (attr === tempAttr) return;                 // пропускаем температуру
              if (!weatherAttrs.includes(attr)) return;      // только штатные метео-поля

              // есть ли данные?
              const hasInState    = stateObj.attributes[attr] != null;
              const hasInForecast = items.some(i => i[attr] != null);
              if (!hasInState && !hasInForecast) return;

              // текущее значение
              const rawVal = hasInState ? stateObj.attributes[attr] : items[0][attr];

              // === NEW: если и текущее, и весь прогноз — нули/пусто, то атрибут не рисуем,
              //           КРОМЕ исключений (например, wind_bearing: 0° — валидно)
              const zeroSkipExceptions = new Set(["wind_bearing"]);     // <-- добавили
              const applyZeroSkip = !zeroSkipExceptions.has(attr);      // <-- добавили

              const toNum = (v) => (typeof v === "number" ? v : (v != null ? Number(v) : NaN));
              const currentNum = toNum(rawVal);
              const seriesNums = items
                .map(i => toNum(i?.[attr]))
                .filter(n => Number.isFinite(n)); // только числа

              const currentNonZero  = Number.isFinite(currentNum) && currentNum !== 0;
              const forecastNonZero = seriesNums.some(n => n !== 0);

              // если правило применяется (не исключение) И всё равно нули/пусто — выходим
              if (applyZeroSkip && !currentNonZero && !forecastNonZero) {
                return;
              }

              // формат текущего значения
              let text;
              if (attr === "precipitation_probability" || attr === "humidity" || attr === "cloud_coverage") {
                text = `${rawVal}%`;
              } else if (attr === "wind_bearing") {
                text = `${rawVal}°`;
              } else if (attr === "precipitation") {
                const unit    = pickUnit(attr);
                const fmtOpts = { minimumFractionDigits: 1, maximumFractionDigits: 1 };
                text = `${this._formatNumberInternal(rawVal, this.hass.locale, fmtOpts)}${unit ? ` ${unit}` : ""}`;
              } else {
                const unit    = pickUnit(attr);
                const fmtOpts = { minimumFractionDigits: digits, maximumFractionDigits: digits };
                text = `${this._formatNumberInternal(rawVal, this.hass.locale, fmtOpts)}${unit ? ` ${unit}` : ""}`;
              }

              // === NEW: min/max по выбранному диапазону items (только значения, без юнитов) ===
              let minText = "", maxText = "";
              {
                const series = items
                  .map(i => i?.[attr])
                  .filter(v => typeof v === "number" && !Number.isNaN(v));

                if (series.length) {
                  const mn = Math.min(...series);
                  const mx = Math.max(...series);

                  // локальный форматтер БЕЗ единиц
                  const fmt = (v) => {
                    if (attr === "precipitation_probability" || attr === "humidity" || attr === "cloud_coverage") {
                      return String(Math.round(v));                          // проценты: целое число
                    }
                    if (attr === "precipitation") {
                      return this._formatNumberInternal(                     // осадки: 1 десятая
                        v,
                        this.hass.locale,
                        { minimumFractionDigits: 1, maximumFractionDigits: 1 }
                      );
                    }
                    return this._formatNumberInternal(                       // прочее: по digits
                      v,
                      this.hass.locale,
                      { minimumFractionDigits: digits, maximumFractionDigits: digits }
                    );
                  };

                  minText = fmt(mn);
                  maxText = fmt(mx);
                }
              }
              const minMaxStack = (minText && maxText)
                ? this._createMinMaxStack(minText, maxText, mode)
                : null;


              // 1) Группируем осадки
              if (attr === "precipitation" || attr === "precipitation_probability") {
                if (!precipContainer) {
                  precipContainer = this._createSectionContainer(
                    "precip-info",
                    mode,
                    `
                      ${mode === "focus"
                        ? `padding-left: 4px;`
                        : `justify-content: flex-start;flex-wrap: wrap; gap: 4px;`
                      }
                    `
                  );
                  // общая иконка осадков
                  const commonIcon = this._createIconContainer(
                    "mdi:weather-rainy",
                    mode,
                    `${mode === "focus" ? `` : `padding-right: 2px;`}`
                  );
                  precipContainer.appendChild(commonIcon);
                  attrContainer.appendChild(precipContainer);
                }
                // value + min/max в одном контейнере
                const valueWrap = document.createElement("div");
                valueWrap.style.cssText = `
                  display: inline-flex;
                  flex-direction: ${mode === "focus" ? "row" : "column"};
                  align-items: ${mode === "focus" ? "baseline" : ""};
                  gap: ${mode === "focus" ? "2px" : ""};
                  flex-wrap: nowrap;
                `;
                const valEl = this._createTextContainer(text, mode);
                valueWrap.appendChild(valEl);
                if (minMaxStack) valueWrap.appendChild(minMaxStack);

                precipContainer.appendChild(valueWrap);

              // 2) Группируем ветер: wind_bearing, wind_speed, wind_gust_speed
              } else if (["wind_bearing", "wind_speed", "wind_gust_speed"].includes(attr)) {
                if (!windContainer) {
                  windContainer = this._createSectionContainer(
                    "wind-info",
                    mode,
                    `
                      ${mode === "focus"
                        ? `padding-left: 4px;`
                        : `justify-content: flex-start; flex-wrap: wrap; gap: 4px;`
                      }
                    `
                  );
                  attrContainer.appendChild(windContainer);
                }

                // элемент для конкретного ветрового атрибута
                const item = document.createElement("div");
                item.style.cssText = `
                  display: flex;
                  align-items: ${mode === "focus" ? "" : "center"};
                  gap: 2px;
                `;

                // === ИКОНКА ===
                let iconEl = null;
                if (attr === "wind_bearing") {
                  // стрелка как иконка: КУДА дует (bearing + 180°)
                  iconEl = createWindDirIcon(rawVal, mode, { toDirection: true }) || document.createElement("ha-icon");
                  if (!iconEl.icon) iconEl.icon = "mdi:compass"; // фолбэк
                  // приводим размеры/отступы к стилю остальных иконок ветра
                  iconEl.style.setProperty("--mdc-icon-size", (mode === "focus" ? "1.1em" : "1.9em"));
                  iconEl.style.flex = (mode === "focus" ? "0 0 1.1em" : "0 0 1.9em");
                  if (mode !== "focus") iconEl.style.paddingRight = "2px";
                } else {
                  const iconName = this._computeAttributeIcon(attr);
                  if (iconName) {
                    iconEl = document.createElement("ha-icon");
                    iconEl.icon = iconName;
                    iconEl.style.cssText = `
                      display: inline-flex;
                      --mdc-icon-size: ${mode === "focus" ? "1.1em" : "1.9em"};
                      flex: ${mode === "focus" ? "0 0 1.1em" : "0 0 1.9em"};
                      ${mode === "focus" ? `` : `padding-right: 2px;`}
                    `;
                  }
                }
                if (iconEl) item.appendChild(iconEl);

                // === ЗНАЧЕНИЕ (текст + min/max) ===
                const valueWrap = document.createElement("div");
                valueWrap.style.cssText = `
                  display: inline-flex;
                  flex-direction: ${mode === "focus" ? "row" : "column"};
                  align-items: ${mode === "focus" ? "baseline" : ""};
                  gap: ${mode === "focus" ? "2px" : ""};
                  flex-wrap: nowrap;
                `;

                if (attr === "wind_bearing") {
                  // только локализованный румб, без градусов
                  const short = toCardinal(rawVal);
                  const label = short ? localizeCardinal(this.hass, short) : (rawVal ?? "") + "";
                  const valEl = this._createTextContainer(label, mode);
                  valueWrap.appendChild(valEl);
                  // min/max для bearing не показываем
                } else {
                  // speed / gust: как раньше
                  const valEl = this._createTextContainer(text, mode);
                  valueWrap.appendChild(valEl);
                  if (minMaxStack) valueWrap.appendChild(minMaxStack);
                }

                item.appendChild(valueWrap);
                windContainer.appendChild(item);

              // 3) Все остальные атрибуты — по-отдельности
              } else {
                const container = this._createSectionContainer(
                  "attr-info",
                  mode,
                  `
                    ${mode === "focus"
                      ? `padding-left: 4px;`
                      : `justify-content: flex-start; gap: 4px;`
                    }
                  `
                );

                // иконка
                const iconName = this._computeAttributeIcon(attr);
                if (iconName) {
                  const iconEl = document.createElement("ha-icon");
                  iconEl.icon = iconName;
                  iconEl.style.cssText = `
                    display: inline-flex;
                    --mdc-icon-size: ${mode === "focus" ? "1.1em" : "1.9em"};
                    flex: ${mode === "focus" ? "0 0 1.1em" : "0 0 1.9em"};
                    ${mode === "focus" ? `` : `padding-right: 1px;`}
                  `;
                  container.appendChild(iconEl);
                }
                // текущее значение
                const valueWrap = document.createElement("div");
                valueWrap.style.cssText = `
                  display: inline-flex;
                  flex-direction: ${mode === "focus" ? "row" : "column"};
                  align-items: ${mode === "focus" ? "baseline" : ""};
                  gap: ${mode === "focus" ? "2px" : ""};
                  flex-wrap: nowrap;
                `;
                const valEl = this._createTextContainer(text, mode);
                valueWrap.appendChild(valEl);
                if (minMaxStack) valueWrap.appendChild(minMaxStack);
              
                container.appendChild(valueWrap);

                attrContainer.appendChild(container);
              }
            });
            // === Итог: добавляем весь attrContainer в header ===
            header.appendChild(attrContainer);
            /* -----------------------------------------------------------
             *  Оверлей: timeFlex + tempFlex + линии min/max/zero
             * --------------------------------------------------------- */
            
            const overlay = document.createElement("div");
            overlay.classList.add("hover-scroll");
            overlay.style.cssText = `
              position: relative;
              flex: 1 1 auto;
              min-width: 0;
              height: ${OVERLAY_H}px;
              box-sizing: border-box;
            `;

            // 1) timeFlex с теми же стилями, что использовались раньше
            const timeFlex = document.createElement("div");
            timeFlex.style.cssText = `
              display:flex;
              flex:1 1 auto; min-width:0; box-sizing:border-box;
              padding-bottom:4px; pointer-events:none;
              padding-inline: 0 ${padStr};
            `;
            items.forEach((i, idx) => {
              const cell = document.createElement("div");
              cell.style.cssText = `
                flex:1 1 0;
                min-width:${cellMinWidth}px;
                width:0;
                display:flex; flex-direction:column;
                align-items:center; text-align:center;
                color:var(--secondary-text-color);
                padding-inline: clamp(1px,2%,5px);
                /* box-sizing:border-box; */
                line-height:1;
                /* еле заметный разделитель справа */
                ${idx < items.length - 1
                  ? `box-shadow: inset -1px 0 0 var(--divider-color);`
                  : ``}                
              `;
              // 1) Метка времени
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
              // 2) Иконка состояния по i.condition, только если не Silam
              if (!isSilamSource) {
                /* ── определяем, ночь ли для КОНКРЕТНОГО слота ─────────────────── */
                const slotNight =
                  (i.is_daytime === false) ||               // явно передано
                  (i.is_daytime === undefined); // иначе глобальный расчёт

                /* ── пробуем отрисовать SVG ─────────────────────────────────────── */
                const svgIcon = getWeatherStateSVG(
                  (i.condition || "").toLowerCase(),
                  slotNight
                );

                let iconNode;

                if (svgIcon instanceof SVGSVGElement && svgIcon.hasChildNodes()) {
                  /* 1) SVG найден — используем его */
                  iconNode = svgIcon;
                  iconNode.setAttribute("width",  "1.7em");
                  iconNode.setAttribute("height", "1.7em");
                  iconNode.style.cssText = `
                    width: 1.7em;
                    height: 1.7em;
                    margin: 2px 0;
                    /* чтобы MDC-CSS не вмешивался */
                    --mdc-icon-size: 0;
                  `;
                } else {
                  /* 2) фолбэк — штатная иконка Home Assistant */
                  iconNode = document.createElement("ha-state-icon");
                  iconNode.hass = this._hass;
                  iconNode.stateObj = {
                    entity_id: this._cfg.entity,
                    state:     i.condition,
                    attributes:{},
                  };
                  iconNode.style.cssText = `
                    --mdc-icon-size: 1.7em;
                    margin-top: 2px;
                    margin-bottom: 2px;
                    --ha-icon-display: block;
                  `;
                }

                cell.appendChild(iconNode);
              }
              
              timeFlex.appendChild(cell);
            });
            overlay.appendChild(timeFlex);

// 1.1) windFlex — между timeFlex и tempFlex (только если пользователь выбрал и есть данные)
if ((hasWind && maxWind > 0) || showWindDir) {
  const windFlex = document.createElement("div");
  windFlex.style.cssText = `
    display:flex;
    align-items:flex-end;
    padding-bottom:4px;
    padding-inline: 0 ${padStr};
    pointer-events:none;
    z-index:3;
  `;

  // по слотам: мини-бар (если выбран speed) + стрелка (если выбран bearing)
  items.forEach((i) => {

    const cell = document.createElement("div");
    cell.style.cssText = `
      flex:1 1 0;
      min-width:${cellMinWidth}px;
      width:0;
      display:flex; flex-direction:column;
      align-items:center; text-align:center;
      color:var(--secondary-text-color);
      padding-inline: clamp(1px,2%,5px);
      /* box-sizing:border-box; */
      line-height:1;
    `;

    // --- STACK контейнер под столбики (нормируем к высоте слоя ветра) ---
    const capTop     = showWindDir ? 15  : -15;
    const usableH  = Math.max(0, WIND_H - capTop);
    // резерв под подпись порыва (только если показываем порывы)
    const GUST_LABEL_H = 10;
    const GUST_GAP     = 2;

    // barsAreaH — реальная высота под столбики (без верхней зоны под подпись порыва)
    const barsAreaH = hasGustBars
      ? Math.max(0, usableH - (GUST_LABEL_H + GUST_GAP))
      : usableH;

    // пересчёт высот
    const speedVal = showWindSpeed ? Math.max(0, Number(i?.wind_speed ?? 0)) : 0;
    const gustVal  = showWindGust  ? Math.max(0, Number(i?.wind_gust_speed ?? (showWindSpeed ? i?.wind_speed : 0))) : 0;

    // конвертация значений в м/с для цвета
    const speedMS = toMS(speedVal, windUnit);
    const gustMS  = toMS(gustVal,  windUnit);

    // номера по Бофорту
    const bSpeed = Number.isFinite(speedMS) ? beaufortFromMS(speedMS) : 0;
    const bGust  = Number.isFinite(gustMS)  ? beaufortFromMS(gustMS)  : bSpeed;

    // цвета: порывы более прозрачные
    const speedColor = beaufortColorWiki(bSpeed, 0.85);
    const gustColor  = beaufortColorWiki(bGust,  0.28);

    // высоты считаем ТОЛЬКО если есть бары
    let hGustRaw = 0, hSpeedRaw = 0;
    if (hasBars && maxWind > 0) {
      hGustRaw  = Math.round((Math.max(speedVal, gustVal) / maxWind) * barsAreaH);
      hSpeedRaw = Math.round((Math.min(speedVal, gustVal || speedVal) / maxWind) * barsAreaH);
    }

// 2) stack с барами — только если есть что рисовать
if (hasBars) {
  const stack = document.createElement("div");
  stack.style.cssText = `
    position: relative; width: 100%; height: ${usableH}px;
  `;
  cell.appendChild(stack);

  // порывы
  if (hasGustBars && hGustRaw > 0) {
    const gustBand = document.createElement("div");
    gustBand.style.cssText = `
      position: absolute;
      left: 50%; transform: translateX(-50%);
      bottom: 0;
      width: clamp(12px,40%,42px); height: ${hGustRaw}px;
      background: ${gustColor};
      border-radius: 3px;
    `;
    stack.appendChild(gustBand);

    // значение порыва на вершине столбца (в выбранных единицах, без юнитов)
    const windDigits = Number(this._cfg?.wind_digits ?? 0);
    const gustText = this._formatNumberInternal(
      gustVal,
      this.hass?.locale || {},
      { minimumFractionDigits: windDigits, maximumFractionDigits: windDigits }
    );
    
    const gustDiff = (this._cfg?.gust_label_threshold ?? 0.5); // м/с или в юнитах источника
    const showGustValue = hasGustBars && (Math.abs(gustVal - speedVal) >= gustDiff);
    
    // аккуратно держим подпись внутри stack
    const approxLblH = 10;                         // примерная высота текста в px
    const topOffset  = 2;                          // зазор над верхом столбца
    const gustBottom = Math.min(
      Math.max(0, usableH - approxLblH),           // не выше верха stack
      hGustRaw + topOffset                         // на уровне верха столбца + зазор
    );

    if (showGustValue) { 
      const gustLabel = document.createElement("div");
      gustLabel.textContent = gustText;              // только число, без юнитов
      gustLabel.style.cssText = `
        position: absolute;
        left: 50%; transform: translateX(-50%);
        bottom: ${gustBottom}px;
        font-size: .60em; line-height: 1;
        text-shadow: 0 1px 1px rgba(0,0,0,.10);
        color: var(--secondary-text-color);
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        pointer-events: none; user-select: none;
      `;
      stack.appendChild(gustLabel);
    }
  }

  // скорость
  if (hasSpeedBars && hSpeedRaw > 0) {
    const speedBar = document.createElement("div");
    speedBar.style.cssText = `
      position: absolute;
      left: 50%; transform: translateX(-50%);
      bottom: 0;
      width: clamp(8px,30%,34px); height: ${hSpeedRaw}px;
      background: ${speedColor};
      border-radius: 2px;
    `;
    stack.appendChild(speedBar);
  }

  // 3) число скорости под барами (в выбранных единицах, без юнитов)
  if (hasSpeedBars) {
    const windDigits = Number(this._cfg?.wind_digits ?? 0);
    const numText = this._formatNumberInternal(
      speedVal,
      this.hass?.locale || {},
      { minimumFractionDigits: windDigits, maximumFractionDigits: windDigits }
    );
    const vLabel = document.createElement("div");
    vLabel.textContent = numText;
    vLabel.style.cssText = `
      margin-top:${VAL_GAP}px;
      font-size:.72em; line-height:1;
      color: var(--primary-text-color);
      white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
      pointer-events:none; user-select:none;
    `;
    cell.appendChild(vLabel);
  }
}

    if (hasDir) {
      const arrow = createWindDir(i?.wind_bearing, {
        toDirection: true,             // «куда дует»
        prefer: "svg",                 // или "mdi" | "auto"
        size: 16,                      // для SVG; для MDI см. mode
        color: "currentColor",
        hass: this._hass || this.hass, // для локализации румба в title
        mode,                          // если выберешь prefer:"mdi"
      });
      if (arrow) {
        // при необходимости можно добавить доп. стили позиционирования
        arrow.style.cssText += 
          `flex:0 0 16px;
          margin-top:2px;
          `;
        cell.appendChild(arrow);
        const deg = parseBearing(i?.wind_bearing);
        if (Number.isFinite(deg)) {
          const short = toCardinal(deg);
          const label = document.createElement("div");
          label.textContent = localizeCardinal(this._hass || this.hass, short);
          label.style.cssText = `
            font-size:.7em; line-height:1;
            margin-top:2px; opacity:.75;
            pointer-events:none; user-select:none;
            white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
            max-width:100%;
          `;
          cell.appendChild(label);
        }
      }
    }

    windFlex.appendChild(cell);
  });
  overlay.appendChild(windFlex);
}

            // 2) tempFlex
            const tempFlex = document.createElement("div");
            tempFlex.style.cssText = `
              display:flex;
              /* gap:clamp(1px,2%,10px);  */
              flex:1 1 auto; min-width:0; box-sizing:border-box;
              padding-top: ${labelPadding}px;
              padding-inline: 0 ${padStr};
              pointer-events:none;
            `;
            items.forEach((i,idx) => {
              const cell = document.createElement("div");
              cell.style.cssText = `
                position: relative;
                flex: 1 1 0;
                min-width: ${cellMinWidth}px;
                width: 0;
                height: ${chartH}px;
                /* box-sizing:border-box; */
                padding-inline: clamp(1px,2%,5px);
              `;              
              if (showTemp && tempAttr) {
                const vHigh  = i[tempAttr] != null ? i[tempAttr] : tMin;
                const hasLow = i.templow != null;
                const vLow   = hasLow ? i.templow : vHigh;
            
                // нормализация и координаты
                const normHigh = (vHigh - tMin) / range;
                const normLow  = (vLow  - tMin) / range;
                const offHigh  = Math.round((1 - normHigh) * (chartH - markerH));
                const offLow   = Math.round((1 - normLow ) * (chartH - markerH));

                const centerHigh = offHigh + markerH / 2;
                const centerLow  = offLow  + markerH / 2;

                const barTop    = Math.min(centerHigh, centerLow);
                const barHeight = Math.abs(centerLow - centerHigh);

                // подсветка экстремумов
                const highlightMax = vHigh === tMax;
                const highlightMin = useLowExtremes
                  ? (vLow === tMin)
                  : (vHigh === tMin);

                const colorHigh = mapTempToColor(vHigh,1,entityTemperatureUnit);
                const colorLow  = mapTempToColor(vLow,1,entityTemperatureUnit);

                const bar = document.createElement("div");
                bar.style.cssText = `
                  position: absolute;
                  top: ${barTop}px;
                  left: 50%;
                  transform: translateX(-50%);
                  width: clamp(30%,40%,50%);
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
                  width: clamp(30%,40%,50%);
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
                    width: clamp(30%,40%,50%);
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

                const maxLine = document.createElement("div");
                maxLine.style.cssText = `
                  position:absolute;
                  top:${markerH/2}px;
                  left:0; right:0;
                  width: 100%;
                  border-top: 1px solid
                    color-mix(
                      in srgb,
                      var(--divider-color) 70%,
                      ${colortMax} 30%
                    );
                  pointer-events:none;
                `;
                cell.appendChild(maxLine);
                const minLine = document.createElement("div");
                minLine.style.cssText = `
                  position:absolute;
                  top:${chartH - markerH/2}px;
                  left:0; right:0;
                  border-top: 1px solid
                    color-mix(
                      in srgb,
                      var(--divider-color) 70%,
                      ${colortMin} 30%
                    );
                  pointer-events:none;
                `;
                cell.appendChild(minLine);
                if (tMin < 0 && tMax > 0) {
                  const zeroNorm = (0 - tMin)/range;
                  const zeroOff = Math.round((1 - zeroNorm)*(chartH - markerH));
                  const zeroLine = document.createElement("div");
                  zeroLine.style.cssText = `
                    position:absolute;
                    top: ${zeroOff + markerH / 2}px;
                    left:0; right:0;
                    border-top: 1px solid
                      color-mix(
                        in srgb,
                        var(--divider-color) 70%,
                        ${colorZero} 30%
                      );
                    pointer-events:none;
                  `;
                  cell.appendChild(zeroLine);
                }
              }
              // --- вероятность осадков + amount scatter на cell ----------------------
              // 1) probability-бар, если есть вероятность И если пользователь добавил precipitation_probability
              if (showProb) {
                const prob   = i.precipitation_probability; // может быть undefined
                let probH = 0;
                if (maxProb > 0 && typeof prob === 'number' && prob > 0) {
                  probH = showTemp ? Math.round((prob / 100) * (chartH - markerH)) : probH = Math.round((prob / maxProb) * (chartH - markerH));
                  const barWidth = showTemp ? precipBarW : 0.3; // 12% если с темпой, 30% если без
                  const precipBar = document.createElement("div");
                  precipBar.style.cssText = `
                    position: absolute;
                    bottom: ${markerH / 2}px;
                    width: ${barWidth * 100}%;
                    height: ${probH}px;
                    background: ${precipColor};
                    border-radius: 2px 2px 0 0;
                    pointer-events: none;
                    ${showTemp
                        ? `right: 4%;`
                        : `left: 50%; transform: translateX(-50%);`
                      }
                  `;
                  cell.appendChild(precipBar);

                  // подпись «42 %» сразу над баром (если он достаточно высокий)
                  if (probH > 24) {
                    const lbl = document.createElement("div");
                    lbl.textContent = `${prob}%`;
                    lbl.style.cssText = `
                      position: absolute;
                      bottom: ${markerH / 2 + probH + 2}px;
                      /* если рисуем вместе с температурой — 12% ширины и сдвиг вправо,
                        иначе — центрируем и делаем ширину auto */
                      ${showTemp
                        ? `right: 4%;
                          width: ${precipBarW * 100}%;`
                        : `left: 50%;
                          transform: translateX(-50%);
                          width: auto;`
                      }
                      text-align: center;
                      font-size: .55em;
                      color: var(--secondary-text-color);
                      pointer-events: none;
                    `;
                    cell.appendChild(lbl);
                  }
                }
              }

              // 2) «Короб» для разбросанных иконок и подписи amount, если есть количество осадков И если пользователь добавил precipitation
              if (showAmount) {
                const amount = i.precipitation;             // может быть undefined
                const isSnow = snowyStates.has(i.condition);
                const lvl    = precipLevel(amount ?? 0, hSlot, isSnow);
                if (typeof amount === "number" && lvl > 0) {
                  const iconBox = document.createElement("div");
                  iconBox.style.cssText = `
                    position: absolute;
                    bottom: -25%;
                    width: 40%;
                    pointer-events: none;

                    /* центрируем единственную иконку */
                    display: flex;
                    align-items: center;
                    justify-content: center;

                    /* цвет и масштаб всей иконки */
                    color: ${isSnow ? "#b3e5fc" : "#2196f3"};
                    font-size: 1.1em; /* можно играть размером: 0.9em…1.2em */
                    line-height: 0;
                    ${showTemp
                      ? `right: -11%;`
                      : `left: 50%;
                        transform: translateX(-50%);`
                    }
                  `;
                  cell.appendChild(iconBox);

                  // берём массивы, что ты подготовил
                  const arr = isSnow ? snowSVG : rainSVG;
                  const idx = Math.max(0, Math.min(lvl, 4)); // clamp 0..4

                  // вставляем одну готовую SVG, задаём явный размер
                  iconBox.innerHTML = sized(arr[idx], 1.1); // 1.1em — подстрой по вкусу

                  // подпись «мм», если накопилось ≥ 1 мм (как раньше)
                  if (amount > 0) {
                    const amtLbl = document.createElement("div");
                    amtLbl.textContent = `${this._formatNumberInternal(
                      amount,
                      this.hass.locale,
                      { maximumFractionDigits: 1 }
                    )}\u00A0${stateObj.attributes.precipitation_unit || ""}`;
                    amtLbl.style.cssText = `
                      position: absolute;
                      bottom: -5px;
                      left: 50%;
                      transform: translateX(-50%);
                      font-size: .55em;
                      color: var(--secondary-text-color);
                      pointer-events: none;
                    `;
                    if (!showTemp) {
                      iconBox.appendChild(amtLbl);
                    }
                  }
                }
              }
              tempFlex.appendChild(cell);
            });
            bars.appendChild(overlay);
            overlay.appendChild(tempFlex);
            wrapper.appendChild(block);
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
            //header.appendChild(nameEl);

            // — иконка для кастомного атрибута —
            const iconEl = document.createElement("ha-icon");
            iconEl.icon = weatherAttrIcons[attr] || "mdi:chart-bar";
            iconEl.style.cssText = `
              --mdc-icon-size: ${mode === "focus" ? "2em" : "3.5em"};
              margin-bottom: ${mode === "focus" ? "0" : "4px"};
            `;
            //header.appendChild(iconEl);

            // — текстовое значение атрибута —
            const valEl = document.createElement("span");
            valEl.textContent = this._hass.formatEntityAttributeValue(stateObj, attr) || "–";
            valEl.style.cssText = `
              font-size: 0.9em;
            `;
            //header.appendChild(valEl);

            // вставляем header в block
            //block.appendChild(header);

            // — контейнер для пользовательского графика по attr —
            const custom = document.createElement("div");
            // TODO: тут реализовать отрисовку графика для данного атрибута
            //block.appendChild(custom);
            //wrapper.appendChild(block);
          }
          // — добавляем каждый block внутрь wrapper, а не сразу в this._body —
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
      .pollen   { color: var(--secondary-text-color); font-size: .9em; margin-top:4px }
      .pollen span, .attrs span { margin-right: 6px; }
      .attrs    { color: var(--secondary-text-color); font-size: .9em; margin-top:4px }
    </style>
    ${arr.map(i => this._rowHTML(i, lang)).join("")}
  `;
  this._body.appendChild(ul);
  }
                          
  _rowHTML(i, lang) {
    const dt   = new Date(i.datetime);
    const date = dt.toLocaleDateString(
      lang,
      withUserTimeZone(this.hass, { weekday:"short", month:"short", day:"numeric" })
    );
    const part = this._cfg.forecast_type === "twice_daily"
      ? (i.is_daytime === false
          ? this._hass.localize("ui.card.weather.night") || "Night"
          : this._hass.localize("ui.card.weather.day")   || "Day")
      : dt.toLocaleTimeString(
          lang,
          withUserTimeZone(this.hass, { hour: "2-digit", minute: "2-digit" })
        );
    const cond = this._cond[i.condition] || i.condition || "";
  
    // Pollen info (как было)
    const pollenSpans = [];
    if (i.pollen_index != null) {
      pollenSpans.push(`<span>${this._indexLbl}: ${i.pollen_index}</span>`);
    }
    for (const [k, lbl] of Object.entries(this._labels)) {
      if (i[k] != null) pollenSpans.push(`<span>${lbl}: ${i[k]}</span>`);
    }
    const pollen = pollenSpans.length
      ? `<div class="pollen">${pollenSpans.join(" ")}</div>`
      : "";
  
    // Дополнительные атрибуты из конфига
    const extraSpans = (this._cfg.additional_forecast || [])
      .filter(attr => i[attr] != null)
      .map(attr => {
        const label = this._hass.formatEntityAttributeName(this.hass.states[this._cfg.entity], attr);
        return `<span>${label}: ${i[attr]}</span>`;
      });
    const extra = extraSpans.length
      ? `<div class="attrs">${extraSpans.join(" ")}</div>`
      : "";
  
    // Собираем итоговый li
    const tempDisplay = i.temperature != null ? `${i.temperature}°` : "—";
    return `
      <li style="margin:6px 0">
        <b>${date} ${part}</b> :
        ${tempDisplay} ${cond}
        ${pollen}
        ${extra}
      </li>
    `;
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
  // Включаем превью в UI
  static getPreview() {
    return true;
  }
  /**
   * При создании новой карточки из UI подставляем первую
   * подходящую weather-сущность silam_pollen_*_forecast
   */
  static getStubConfig(hass) {
    const ent = Object.keys(hass.states)
      .filter(id => id.startsWith("weather."));
    const randomEntity = ent.length
    ? ent[Math.floor(Math.random() * ent.length)]
    : "";
    return {
      type: "custom:absolute-forecast-card",
      only_silam: false,
      entity: randomEntity,
      forecast_type: "hourly",
      forecast_slots: 5,
      display_attribute: "",
      additional_forecast: ["temperature"],   // ← сразу с температурой
      additional_forecast_mode: "focus",      // ← режим блока
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
      only_silam:     false, // по-умолчанию показываем только нашу интеграцию
      forecast:  "show_both",  // по умолчанию только прогноз
      additional_forecast: [],            // по умолчанию пусто
      additional_forecast_mode: "standard", // режим дополнительного блока
      value_attributes_left:  [],  // новые поля
      value_attributes_right: [],
      value_attributes_as_rows : false,
      debug_forecast:  false,          // ⬅ было позже, перенесли выше
      show_decimals:   false           // ⬅ новый параметр
    };
    this._forecastSample = null; // атрибуты из первого пакета прогноза
    this._unsubForecast  = null; // функция-отписка от WS
  }

  setConfig(config) {
    this._config = {
      only_silam:        false,
      forecast:         "show_both",
      forecast_slots: 5,
      additional_forecast: [],
      additional_forecast_mode: "standard",
      value_attributes_left: [],
      value_attributes_right: [],
      value_attributes_as_rows : false,
      debug_forecast:  false,
      show_decimals:   false,
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

  /**
   * Собирает опции атрибутов для селектора.
   * @param {string} entityId — entity_id
   * @param {boolean} [includeAll=false] — если true, возвращает все атрибуты без фильтрации
   * @returns {Array<{value:string,label:string}>}
   */
  _combineAttributeOptions(entityId, includeAll = false) {
    const stateObj = this.hass.states[entityId];
    if (!stateObj || !stateObj.attributes) {
      return [];
    }
    const weatherProps = [
      "cloud_coverage","humidity","apparent_temperature","dew_point",
      "pressure","temperature","visibility","wind_gust_speed",
      "wind_speed","ozone","uv_index","wind_bearing",
      "precipitation_probability","precipitation",
    ];
    const seen = new Set();
    const baseKeys     = Object.keys(stateObj.attributes);
    const forecastKeys = this._forecastSample ? Object.keys(this._forecastSample) : [];
    const allKeys      = [...new Set([...baseKeys, ...forecastKeys])];

    return allKeys
      .filter((attr) => {
        if (attr.endsWith("_unit")) {
          return false;
        }
        // 2) остальная логика как была
        if (includeAll) {
          return true;                 // без дальнейшей фильтрации
        }
        // иначе — только из списка weatherProps или начинающиеся с pollen_
        return weatherProps.includes(attr) || attr.startsWith("pollen_");
      })
      .map((a) => {
        if (seen.has(a)) return null;
        seen.add(a);
        return {
          value: a,
          label: this.hass.formatEntityAttributeName(stateObj, a),
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
    const full_options = this._combineAttributeOptions(this._config.entity, true);
    // 1) базовые поля
    const baseSchema = [
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

    // 2) advancedSchema 
    const advancedSchema = [
      {
        name:  "value_attributes_left",
        label: this.hass.localize("Левая колонка"),
        selector: {
          select: {
            reorder:     true,
            multiple:    true,
            custom_value:true,
            options: full_options      // этот массив вы уже вычисляете выше
          }
        },
        default: this._config.value_attributes_left,
      },
      {
        name:  "value_attributes_right",
        label: this.hass.localize("Правая колонка"),
        selector: {
          select: {
            reorder:     true,
            multiple:    true,
            custom_value:true,
            options: full_options
          }
        },
        default: this._config.value_attributes_right,
      },
      {
        name: "value_attributes_as_rows",
        selector: { boolean: {} },
        default: false,
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
      /* -------- НОВЫЙ раскрывающийся раздел “Доп.-настройки” -------- */
      {
        name:     "advanced_options",
        type:     "expandable",
        iconPath: "mdi:tune-variant",
        flatten:  true,
        schema: [
          {
            name: "only_silam",
            selector: { boolean: {} },
            default: this._config.only_silam,
          },
          {
            name:  "debug_forecast",
            label: this.hass.localize("component.silam_pollen.editor.debug_forecast"),
            selector: { boolean: {} },
            default: this._config.debug_forecast,
          },
          {
            name:  "show_decimals",
            label: "Показывать десятые дроби",
            selector: { boolean: {} },
            default: this._config.show_decimals,
          },
        ],
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
  description: "Absolute forecast card (uses native weather selector)",
  preview: true,                    // ⬅⬅ ВКЛЮЧАЕТ превью в каталоге
  documentationURL: "https://github.com/danishru/silam_pollen"     // (необязательно, но полезно)
});