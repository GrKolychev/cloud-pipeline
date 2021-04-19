/*
 * Copyright 2017-2021 EPAM Systems, Inc. (https://www.epam.com/)
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 *  Unless required by applicable law or agreed to in writing, software
 *  distributed under the License is distributed on an "AS IS" BASIS,
 *  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 *  See the License for the specific language governing permissions and
 *  limitations under the License.
 */

import modificationsRenderConfig from './modifications-render-config';
import ModificationType from './changes/types';
import ChangeStatuses from './changes/statuses';
import {Merged} from './conflicted-file/branches';

function getStyleForModificationType (type) {
  switch (type) {
    case ModificationType.edition: return modificationsRenderConfig.edition;
    case ModificationType.conflict: return modificationsRenderConfig.conflict;
    case ModificationType.deletion: return modificationsRenderConfig.deletion;
    case ModificationType.insertion: return modificationsRenderConfig.insertion;
    default:
      break;
  }
  return undefined;
}

function correctPixels (pixels) {
  return pixels * window.devicePixelRatio;
}

function centerPoint (p1, p2) {
  const {x: p1x, y: p1y} = p1;
  const {x: p2x, y: p2y} = p2;
  return {
    x: (p1x + p2x) / 2.0,
    y: (p1y + p2y) / 2.0
  };
}

function findIntermediatePoint (p1, p2, length) {
  const {x: p1x, y: p1y} = p1;
  const {x: p2x, y: p2y} = p2;
  const dx = p2x - p1x;
  const dy = p2y - p1y;
  const totalLength = Math.sqrt(dx ** 2 + dy ** 2);
  const ratio = Math.max(0, Math.min(1, length / totalLength));
  return {
    x: p1x + dx * ratio,
    y: p1y + dy * ratio
  };
}

function drawCurve (context, start, end, options = {}) {
  const {
    reverse = false,
    lineToFirstPoint = false
  } = options;
  const {x: sX, y: sY} = reverse ? end : start;
  const {x: eX, y: eY} = reverse ? start : end;
  const dx = eX - sX;
  const offset = dx / 3.0;
  const s1 = {
    x: sX + offset,
    y: sY
  };
  const e1 = {
    x: eX - offset,
    y: eY
  };
  const center = centerPoint(s1, e1);
  const s2 = findIntermediatePoint(s1, center, Math.abs(offset));
  const e2 = findIntermediatePoint(e1, center, Math.abs(offset));
  if (lineToFirstPoint) {
    context.lineTo(sX, sY);
  } else {
    context.moveTo(sX, sY);
  }
  context.quadraticCurveTo(s1.x, s1.y, s2.x, s2.y);
  context.lineTo(e2.x, e2.y);
  context.quadraticCurveTo(e1.x, e1.y, eX, eY);
}

function getModificationIndexRanges (modification, branch) {
  const start = modification.items[0];
  const previous = start.previous[branch] || start;
  const end = modification.items[modification.items.length - 1];
  return {
    start: previous.lineNumber[branch],
    end: end.lineNumber[branch]
  };
}

export default function renderModifications (canvas, list, modifications, branch, options = {}) {
  if (canvas && canvas.getContext) {
    const {
      width = canvas.width / window.devicePixelRatio,
      top = 0,
      mergedTop = 0,
      lineHeight = 0,
      rtl = false
    } = options;
    const x1 = rtl ? correctPixels(width) : 0;
    const x2 = rtl ? 0 : correctPixels(width);
    const context = canvas.getContext('2d');
    if (context) {
      context.save();
      context.clearRect(0, 0, canvas.width, canvas.height);
      context.fillStyle = modificationsRenderConfig.background;
      context.rect(0, 0, canvas.width, canvas.height);
      context.fill();
      const currentModifications = (modifications || [])
        .filter(m => m.branch === branch);
      for (let i = 0; i < currentModifications.length; i++) {
        const modification = currentModifications[i];
        if (modification.items.length > 0) {
          const current = getModificationIndexRanges(modification, branch);
          const merged = getModificationIndexRanges(modification, Merged);
          const currentModificationsBefore = modification.changesBefore[branch] || 0;
          const mergedModificationsBefore = modification.changesBefore[Merged] || 0;
          const currentY1 = current.start * lineHeight +
            currentModificationsBefore * 2.0 + 0.5 - top;
          const currentY2 = current.end * lineHeight +
            (currentModificationsBefore + 1) * 2.0 - 0.5 - top;
          const mergedY1 = merged.start * lineHeight +
            mergedModificationsBefore * 2.0 + 0.5 - mergedTop;
          const mergedY2 = merged.end * lineHeight +
            (mergedModificationsBefore + 1) * 2.0 - 0.5 - mergedTop;
          const config = getStyleForModificationType(modification.type);
          const applied = modification.status !== ChangeStatuses.prepared;
          if (config) {
            const start1 = {
              x: x1,
              y: correctPixels(currentY1)
            };
            const start2 = {
              x: x1,
              y: correctPixels(currentY2)
            };
            const end1 = {
              x: x2,
              y: correctPixels(mergedY1)
            };
            const end2 = {
              x: x2,
              y: correctPixels(mergedY2)
            };
            context.fillStyle = applied
              ? modificationsRenderConfig.background
              : config.background;
            context.beginPath();
            drawCurve(context, start1, end1);
            drawCurve(context, start2, end2, {reverse: true, lineToFirstPoint: true});
            context.closePath();
            context.fill();
            context.lineWidth = correctPixels(1);
            context.strokeStyle = applied ? config.applied : config.color;
            if (applied) {
              context.setLineDash([5]);
            }
            context.beginPath();
            drawCurve(context, start1, end1);
            drawCurve(context, start2, end2);
            context.stroke();
            context.setLineDash([]);
          }
        }
      }
      context.restore();
    }
  }
}
