import {
  Body,
  Controller,
  Delete,
  Get,
  HttpStatus,
  ParseFilePipeBuilder,
  Post,
  Put,
  UploadedFile,
  UseInterceptors,
} from '@nestjs/common';
import { FileInterceptor } from '@nestjs/platform-express';
import { RoutesService } from './routes.service';
import { CreateRouteDto } from 'src/dto/create-route.dto';

@Controller('routes')
export class RoutesController {
  constructor(private readonly routesService: RoutesService) {}

  @Post('upload')
  @UseInterceptors(FileInterceptor('file'))
  uploadFile(
    @UploadedFile(
      new ParseFilePipeBuilder()
        .addFileTypeValidator({
          fileType: 'image',
        })
        .build({
          errorHttpStatusCode: HttpStatus.UNPROCESSABLE_ENTITY,
        }),
    )
    file: Express.Multer.File,
    @Body() body: CreateRouteDto,
  ) {
    return this.routesService.create({ ...file, ...body });
  }

  @Put('route')
  update(@Body() body) {
    return this.routesService.updateOne(body);
  }

  @Get('route')
  findOne(@Body() body) {
    return this.routesService.findOne(body.id);
  }

  @Delete('route')
  deleteOne(@Body() body) {
    return this.routesService.deleteOne(body.id);
  }

  @Get()
  findRoutes() {
    return this.routesService.findAll();
  }
}
